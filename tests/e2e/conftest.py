"""E2E test fixtures — requires live Docker Compose stack."""

import time
import pytest
import httpx
import jwt

BASE_URL = "http://localhost:8000/api/v1"
JWT_SECRET = "dev-secret-change-in-production"
LITELLM_URL = "http://localhost:4000"
LITELLM_MASTER_KEY = "sk-flowforge-local"


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

    # Also require LiteLLM to be able to serve chat completions.
    # The e2e suite asserts an actual LLM reply, so missing provider credentials
    # should skip rather than hang.
    try:
        resp = _httpx.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
            json={
                "model": "default",
                "messages": [{"role": "user", "content": "ping"}],
            },
            timeout=10.0,
        )
        if resp.status_code >= 400:
            pytest.skip(
                f"LiteLLM is running but cannot complete requests ({resp.status_code}): {resp.text}",
                allow_module_level=True,
            )
    except (_httpx.ConnectError, _httpx.TimeoutException) as e:
        pytest.skip(
            f"LiteLLM not reachable ({e}) — skipping all e2e tests",
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
    # The docker-compose stack seeds a default tenant with this fixed UUID.
    # E2E tests mint JWTs directly, so they must use a tenant_id that exists.
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
def auth_headers(tenant_id: str) -> dict:
    token = _mint_jwt(tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def http(auth_headers: dict):
    with httpx.Client(base_url=BASE_URL, headers=auth_headers, timeout=30.0) as client:
        yield client
