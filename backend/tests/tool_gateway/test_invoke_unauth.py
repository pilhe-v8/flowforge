from fastapi.testclient import TestClient


def test_invoke_requires_auth():
    from flowforge.tool_gateway.main import app

    client = TestClient(app)
    resp = client.post(
        "/v1/tool-calls:invoke",
        json={"tool_uri": "mcp://example/tool", "inputs": {"q": "hi"}},
    )

    assert resp.status_code == 401
