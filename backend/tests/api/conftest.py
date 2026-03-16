"""Shared fixtures for API tests."""

import time
import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
import jwt
from fastapi.testclient import TestClient

from flowforge.main import app
from flowforge.api.deps import get_current_user, get_tenant_id
from flowforge.db.session import get_db

JWT_SECRET = "dev-secret-change-in-production"
TENANT_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())


def make_token(role: str = "editor", tenant_id: str = TENANT_ID) -> str:
    payload = {
        "sub": USER_ID,
        "tenant_id": tenant_id,
        "role": role,
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def fake_user(role: str = "editor", tenant_id: str = TENANT_ID) -> dict:
    return {
        "sub": USER_ID,
        "tenant_id": tenant_id,
        "role": role,
        "exp": int(time.time()) + 3600,
    }


def make_mock_db():
    """Return an AsyncMock that behaves like an AsyncSession."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def tenant_id() -> str:
    return TENANT_ID


@pytest.fixture
def auth_headers() -> dict:
    return {"Authorization": f"Bearer {make_token('editor')}"}


@pytest.fixture
def admin_headers() -> dict:
    return {"Authorization": f"Bearer {make_token('admin')}"}
