from fastapi.testclient import TestClient


def test_health_returns_ok():
    from flowforge.tool_gateway.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
