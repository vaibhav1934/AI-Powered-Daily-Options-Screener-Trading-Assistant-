"""
API Security
=============
Simple API key authentication for single-user v1.
Future: extend to OAuth/JWT for multi-user support.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.services.auth_service import get_user_by_username, verify_token

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(API_KEY_HEADER),
) -> str:
    """
    FastAPI dependency — validates the API key from request header.
    Single-user v1: compares against APP_SECRET_KEY from config.
    """
    settings = get_settings()
    if not api_key or api_key != settings.app.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": "Invalid or missing API key. Provide X-API-Key header.",
                }
            },
        )
    return api_key


async def verify_authenticated_or_api_key(
    authorization: str | None = Header(None, alias="Authorization"),
    api_key: str | None = Security(API_KEY_HEADER),
    session: AsyncSession = Depends(get_db),
) -> str:
    """Accept either a valid JWT bearer token or the configured API key."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        payload = verify_token(token, expected_type="access")
        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "AUTHENTICATION_ERROR",
                        "message": "Access token is missing subject identity.",
                    }
                },
            )
        user = await get_user_by_username(session, str(username))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "AUTHENTICATION_ERROR",
                        "message": "User account is inactive or no longer exists.",
                    }
                },
            )
        return token

    return await verify_api_key(api_key)


async def require_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Require a valid JWT bearer token and return the active authenticated user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": "Missing or invalid Bearer authentication header.",
                }
            },
        )

    token = authorization[7:].strip()
    payload = verify_token(token, expected_type="access")
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": "Access token is missing subject identity.",
                }
            },
        )

    user = await get_user_by_username(session, str(username))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": "User account is inactive or no longer exists.",
                }
            },
        )

    return user
