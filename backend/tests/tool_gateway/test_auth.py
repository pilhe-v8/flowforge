import time

import jwt
from fastapi.testclient import TestClient


def _make_token(payload: dict, *, secret: str) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def test_invoke_rejects_invalid_token():
    from flowforge.tool_gateway.main import app

    client = TestClient(app)
    resp = client.post(
        "/v1/tool-calls:invoke",
        headers={"Authorization": "Bearer not-a-jwt"},
        json={"tool_uri": "mcp://example/tool", "inputs": {"q": "hi"}},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


def test_invoke_rejects_expired_token():
    from flowforge.config import get_settings
    from flowforge.tool_gateway.main import app

    settings = get_settings()
    now = int(time.time())
    token = _make_token({"sub": "user", "exp": now - 10}, secret=settings.jwt_secret)

    client = TestClient(app)
    resp = client.post(
        "/v1/tool-calls:invoke",
        headers={"Authorization": f"Bearer {token}"},
        json={"tool_uri": "mcp://example/tool", "inputs": {"q": "hi"}},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expired"


def test_invoke_allows_valid_token_through_to_501():
    from flowforge.config import get_settings
    from flowforge.tool_gateway.main import app

    settings = get_settings()
    now = int(time.time())
    token = _make_token({"sub": "user", "exp": now + 3600}, secret=settings.jwt_secret)

    client = TestClient(app)
    resp = client.post(
        "/v1/tool-calls:invoke",
        headers={"Authorization": f"Bearer {token}"},
        json={"tool_uri": "mcp://example/tool", "inputs": {"q": "hi"}},
    )

    assert resp.status_code == 501
