import jwt
from fastapi.testclient import TestClient


def _make_token(payload: dict, *, secret: str) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def _jwt_secret(monkeypatch) -> str:
    # Keep tests independent from local .env and avoid insecure key warnings.
    secret = "test-secret-please-change-32bytes-min!"
    monkeypatch.setenv("FLOWFORGE_JWT_SECRET", secret)

    # Settings are cached; ensure env overrides are applied.
    from flowforge.config import get_settings

    get_settings.cache_clear()
    return secret


def test_invoke_rejects_invalid_token(monkeypatch):
    from flowforge.tool_gateway.main import app

    client = TestClient(app)
    resp = client.post(
        "/v1/tool-calls:invoke",
        headers={"Authorization": "Bearer not-a-jwt"},
        json={"tool_uri": "mcp://example/tool", "inputs": {"q": "hi"}},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


def test_invoke_rejects_expired_token(monkeypatch):
    from flowforge.tool_gateway.main import app

    secret = _jwt_secret(monkeypatch)
    token = _make_token({"sub": "user", "exp": 0}, secret=secret)

    client = TestClient(app)
    resp = client.post(
        "/v1/tool-calls:invoke",
        headers={"Authorization": f"Bearer {token}"},
        json={"tool_uri": "mcp://example/tool", "inputs": {"q": "hi"}},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expired"


def test_invoke_allows_valid_token_through_to_501(monkeypatch):
    from flowforge.tool_gateway.main import app

    secret = _jwt_secret(monkeypatch)
    token = _make_token({"sub": "user"}, secret=secret)

    client = TestClient(app)
    resp = client.post(
        "/v1/tool-calls:invoke",
        headers={"Authorization": f"Bearer {token}"},
        json={"tool_uri": "mcp://example/tool", "inputs": {"q": "hi"}},
    )

    assert resp.status_code == 501
    assert resp.json()["detail"] == "Tool gateway auth/dispatch not implemented"
