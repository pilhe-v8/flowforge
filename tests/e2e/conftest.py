"""E2E test fixtures — requires live Docker Compose stack."""

import time
import uuid
import pytest
import httpx
import jwt

BASE_URL = "http://localhost:8000/api/v1"
JWT_SECRET = "dev-secret-change-in-production"


@pytest.fixture(scope="session", autouse=True)
def require_stack() -> None:
    """Skip all e2e tests if the Docker Compose stack is not running."""
    import httpx as _httpx

    try:
        _httpx.get(f"{BASE_URL}/workflows", timeout=5.0)
    except (_httpx.ConnectError, _httpx.TimeoutException):
        pytest.skip(
            "Docker Compose stack not running — skipping all e2e tests",
            allow_module_level=True,
        )


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
def http(auth_headers: dict):
    with httpx.Client(base_url=BASE_URL, headers=auth_headers, timeout=30.0) as client:
        yield client
