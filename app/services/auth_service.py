"""
Authentication & JWT Service
=============================
Handles PBKDF2-HMAC-SHA256 password hashing (zero external C-dependencies),
JWT Access/Refresh token creation and verification, and database user queries.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.db.models import User

logger = logging.getLogger(__name__)

# Constants for password hashing
SALT_SIZE = 16
HASH_ITERATIONS = 100_000
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenExpiredError(AuthenticationError):
    error_code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    error_code = "INVALID_TOKEN"


class InvalidCredentialsError(AuthenticationError):
    error_code = "INVALID_CREDENTIALS"


class UserNotFoundError(AuthenticationError):
    error_code = "USER_INACTIVE_OR_NOT_FOUND"


class UserAlreadyExistsError(AuthenticationError):
    status_code = 409
    error_code = "USER_ALREADY_EXISTS"


class RegistrationValidationError(AuthenticationError):
    status_code = 400
    error_code = "REGISTRATION_VALIDATION_ERROR"


def hash_password(password: str) -> str:
    """Hash a password using salted PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(SALT_SIZE)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        HASH_ITERATIONS,
    )
    return f"pbkdf2$100000${salt}${key.hex()}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plain password against a stored PBKDF2 hash."""
    try:
        parts = password_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        stored_key_hex = parts[3]

        computed_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return hmac.compare_digest(computed_key.hex(), stored_key_hex)
    except Exception as e:
        logger.warning("Error verifying password: %s", str(e))
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.app.api_secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.app.api_secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """Verify a JWT token and return its payload if valid and of expected type."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.app.api_secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise InvalidTokenError(
                f"Expected token type '{expected_type}', but got '{payload.get('type')}'."
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("The authentication token has expired. Please log in or refresh.")
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid authentication token: {str(e)}")


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    """Retrieve a user from the database by username."""
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def authenticate_user(
    session: AsyncSession, username: str, password: str
) -> Optional[User]:
    """Authenticate a user by username and password."""
    user = await get_user_by_username(session, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def create_user_in_db(
    session: AsyncSession, username: str, password: str, is_active: bool = True
) -> User:
    """Create a new user or update existing user password in database."""
    existing_user = await get_user_by_username(session, username)
    password_hash = hash_password(password)
    if existing_user:
        existing_user.password_hash = password_hash
        existing_user.is_active = is_active
        await session.commit()
        await session.refresh(existing_user)
        logger.info("Updated existing user credentials for '%s'", username)
        return existing_user

    new_user = User(
        username=username,
        password_hash=password_hash,
        is_active=is_active,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    logger.info("Created new user account for '%s'", username)
    return new_user


async def register_user(
    session: AsyncSession,
    username: str,
    password: str,
) -> User:
    """Register a brand-new user with basic validation and uniqueness checks."""
    normalized_username = username.strip()
    if len(normalized_username) < 3 or len(normalized_username) > 50:
        raise RegistrationValidationError("Username must be between 3 and 50 characters.")
    if not normalized_username.replace("_", "").replace("-", "").isalnum():
        raise RegistrationValidationError("Username may contain only letters, numbers, hyphens, and underscores.")
    if len(password) < 8:
        raise RegistrationValidationError("Password must be at least 8 characters long.")

    existing_user = await get_user_by_username(session, normalized_username)
    if existing_user is not None:
        raise UserAlreadyExistsError("That username is already registered.")

    new_user = User(
        username=normalized_username,
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    logger.info("Registered new user account for '%s'", normalized_username)
    return new_user
