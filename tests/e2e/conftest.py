"""E2E test fixtures — requires live Docker Compose stack."""

import time
import uuid
import pytest
import httpx
import jwt

BASE_URL = "http://localhost:8000/api/v1"
JWT_SECRET = "dev-secret-change-in-production"


def _mint_jwt(tenant_id: str) -> str:
    """Mint a short-lived JWT for the given tenant (HS256, signed with dev secret)."""
    payload = {
        "sub": f"e2e-user-{tenant_id}",
        "tenant_id": tenant_id,
        "role": "editor",
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


@pytest.fixture(scope="session")
def tenant_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="session")
def auth_headers(tenant_id: str) -> dict:
    token = _mint_jwt(tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def http(auth_headers: dict) -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers=auth_headers,
        timeout=30.0,
    )
