"""
Authentication API Endpoints
=============================
Provides JWT Access/Refresh token login, token refreshing, and user profile verification.
No public registration API is exposed (user creation is CLI-only per institutional security).
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.db.models import User
from app.db.schemas import (
    LoginRequestSchema,
    RegisterRequestSchema,
    RefreshTokenRequestSchema,
    TokenResponseSchema,
    UserProfileSchema,
)
from app.core.config import get_settings
from app.db.session import get_db
from app.services.auth_service import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    InvalidCredentialsError,
    InvalidTokenError,
    RegistrationValidationError,
    UserNotFoundError,
    UserAlreadyExistsError,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_user_by_username,
    register_user,
    verify_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Dependency to validate JWT Bearer token and retrieve current active user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("Missing or invalid Bearer authentication header. Please log in.")

    token = authorization[7:].strip()
    payload = verify_token(token, expected_type="access")
    username = payload.get("sub")
    if not username:
        raise InvalidTokenError("Authentication token is missing subject identity.")

    user = await get_user_by_username(session, str(username))
    if not user or not user.is_active:
        raise UserNotFoundError("User account is inactive or no longer exists.")

    return user


@router.post("/login", response_model=TokenResponseSchema)
async def login(
    payload: LoginRequestSchema,
    session: AsyncSession = Depends(get_db),
) -> TokenResponseSchema:
    """
    Authenticate trader credentials and return JWT Access and Refresh tokens.
    """
    user = await authenticate_user(session, payload.username, payload.password)
    if not user:
        logger.warning("Failed login attempt for username '%s'", payload.username)
        raise InvalidCredentialsError("Invalid username or password.")

    access_token = create_access_token({"sub": user.username})
    refresh_token = create_refresh_token({"sub": user.username})

    logger.info("Trader '%s' authenticated successfully", user.username)
    return TokenResponseSchema(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=TokenResponseSchema, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequestSchema,
    session: AsyncSession = Depends(get_db),
) -> TokenResponseSchema:
    """Public self-registration endpoint for multi-user access."""
    settings = get_settings()
    if not settings.app.public_registration_enabled:
        raise RegistrationValidationError("Public registration is currently disabled.")

    user = await register_user(session, payload.username, payload.password)
    access_token = create_access_token({"sub": user.username})
    refresh_token = create_refresh_token({"sub": user.username})

    logger.info("Trader '%s' registered successfully", user.username)
    return TokenResponseSchema(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponseSchema)
async def refresh_token(
    payload: RefreshTokenRequestSchema,
    session: AsyncSession = Depends(get_db),
) -> TokenResponseSchema:
    """
    Exchange a valid Refresh token for a new pair of Access and Refresh tokens.
    """
    token_data = verify_token(payload.refresh_token, expected_type="refresh")
    username = token_data.get("sub")
    if not username:
        raise InvalidTokenError("Refresh token is missing subject identity.")

    user = await get_user_by_username(session, str(username))
    if not user or not user.is_active:
        raise UserNotFoundError("User account is inactive or no longer exists.")

    new_access = create_access_token({"sub": user.username})
    new_refresh = create_refresh_token({"sub": user.username})

    logger.info("Refreshed JWT tokens for trader '%s'", user.username)
    return TokenResponseSchema(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserProfileSchema)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfileSchema:
    """
    Retrieve current authenticated trader profile.
    """
    return UserProfileSchema(
        username=current_user.username,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )
