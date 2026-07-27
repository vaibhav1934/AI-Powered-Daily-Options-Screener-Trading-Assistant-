"""
Unit & Integration Tests for JWT Authentication & Access Control
==============================================================
Tests password hashing, JWT Access & Refresh token generation,
POST /v1/auth/login, POST /v1/auth/refresh, and GET /v1/auth/me
using a deterministic in-memory session override.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db
from app.db.models import User
from app.services.auth_service import hash_password, verify_password

client = TestClient(app)


class MockResult:
    def __init__(self, scalar_val=None):
        self._scalar_val = scalar_val

    def scalar_one_or_none(self):
        return self._scalar_val

    def scalar(self):
        return self._scalar_val


class MockUserSession:
    def __init__(self):
        self.users = {}

    async def execute(self, stmt):
        stmt_str = str(stmt).lower()
        if "users" in stmt_str or "user" in stmt_str:
            params = {}
            try:
                params = stmt.compile().params
            except Exception:
                pass
            for k, val in params.items():
                if isinstance(val, str) and val in self.users:
                    return MockResult(scalar_val=self.users[val])
            # Check if username is in users dict directly
            for username, user_obj in self.users.items():
                if username in stmt_str:
                    return MockResult(scalar_val=user_obj)
        return MockResult(scalar_val=None)

    def add(self, obj):
        if isinstance(obj, User):
            if not obj.id:
                obj.id = len(self.users) + 1
            if not obj.created_at:
                obj.created_at = datetime.now(timezone.utc)
            self.users[obj.username] = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def close(self):
        pass


mock_session = MockUserSession()


async def override_get_db():
    yield mock_session


@pytest.fixture(autouse=True)
def setup_test_users():
    app.dependency_overrides[get_db] = override_get_db
    mock_session.users.clear()
    # Pre-seed testuser
    user = User(
        id=1,
        username="testuser",
        password_hash=hash_password("correctpass"),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    mock_session.users["testuser"] = user
    yield
    mock_session.users.clear()
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]


def test_password_hashing_and_verification():
    """Verify PBKDF2 hashing produces distinct hashes and verifies correctly."""
    pwd = "MySecretPassword123!"
    hashed = hash_password(pwd)
    assert hashed.startswith("pbkdf2$100000$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_auth_login_success():
    """Verify login endpoint returns access and refresh tokens for valid credentials."""
    resp = client.post("/v1/auth/login", json={"username": "testuser", "password": "correctpass"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_auth_login_failure():
    """Verify login fails with 401 for invalid credentials."""
    resp = client.post("/v1/auth/login", json={"username": "testuser", "password": "wrongpass"})
    assert resp.status_code == 401
    assert "error" in resp.json()
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_auth_refresh_and_me():
    """Verify token refreshing and accessing protected profile endpoint."""
    login_resp = client.post("/v1/auth/login", json={"username": "testuser", "password": "correctpass"})
    assert login_resp.status_code == 200
    tokens = login_resp.json()

    # Try /me with access token
    me_resp = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "testuser"
    assert me_resp.json()["is_active"] is True

    # Try refresh token exchange
    refresh_resp = client.post(
        "/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens

    # Try /me with NEW access token
    me_resp2 = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
    )
    assert me_resp2.status_code == 200
    assert me_resp2.json()["username"] == "testuser"
