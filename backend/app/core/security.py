"""
API Security
=============
Simple API key authentication for single-user v1.
Future: extend to OAuth/JWT for multi-user support.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import get_settings

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
