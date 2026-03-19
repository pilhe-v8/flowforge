import pytest


@pytest.mark.parametrize(
    "executor_result",
    [
        {"ok": True, "value": 123},
    ],
)
def test_invoke_executes_tool_and_returns_output(executor_result):
    from fastapi.testclient import TestClient

    from flowforge.tool_gateway.api import get_tool_executor
    from flowforge.tool_gateway.auth import get_current_user
    from flowforge.tool_gateway.main import app

    class FakeExecutor:
        async def execute(self, tool_uri: str, inputs: dict, auth: dict | None = None) -> dict:
            assert tool_uri == "mcp://example/tool"
            assert inputs == {"q": "hi"}
            return executor_result

    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1"}
    app.dependency_overrides[get_tool_executor] = lambda: FakeExecutor()
    try:
        client = TestClient(app)
        resp = client.post(
            "/v1/tool-calls:invoke",
            json={"tool_uri": "mcp://example/tool", "inputs": {"q": "hi"}},
        )
    finally:
        app.dependency_overrides = {}

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["output"] == executor_result
    assert isinstance(data["tool_call_id"], str) and data["tool_call_id"]


def test_invoke_maps_value_error_to_400():
    from fastapi.testclient import TestClient

    from flowforge.tool_gateway.api import get_tool_executor
    from flowforge.tool_gateway.auth import get_current_user
    from flowforge.tool_gateway.main import app

    class FakeExecutor:
        async def execute(self, tool_uri: str, inputs: dict, auth: dict | None = None) -> dict:
            raise ValueError("Unknown protocol in URI: ftp://nope")

    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1"}
    app.dependency_overrides[get_tool_executor] = lambda: FakeExecutor()
    try:
        client = TestClient(app)
        resp = client.post(
            "/v1/tool-calls:invoke",
            json={"tool_uri": "ftp://nope", "inputs": {}},
        )
    finally:
        app.dependency_overrides = {}

    assert resp.status_code == 400


def test_invoke_maps_unexpected_errors_to_502():
    from fastapi.testclient import TestClient

    from flowforge.tool_gateway.api import get_tool_executor
    from flowforge.tool_gateway.auth import get_current_user
    from flowforge.tool_gateway.main import app

    class FakeExecutor:
        async def execute(self, tool_uri: str, inputs: dict, auth: dict | None = None) -> dict:
            raise RuntimeError("boom")

    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1"}
    app.dependency_overrides[get_tool_executor] = lambda: FakeExecutor()
    try:
        client = TestClient(app)
        resp = client.post(
            "/v1/tool-calls:invoke",
            json={"tool_uri": "mcp://example/tool", "inputs": {}},
        )
    finally:
        app.dependency_overrides = {}

    assert resp.status_code == 502


def test_invoke_log_tool_returns_ok_with_auth_override():
    from fastapi.testclient import TestClient

    from flowforge.tool_gateway.auth import get_current_user
    from flowforge.tool_gateway.main import app

    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1"}
    try:
        client = TestClient(app)
        resp = client.post(
            "/v1/tool-calls:invoke",
            json={"tool_uri": "log", "inputs": {"message": "hi"}},
        )
    finally:
        app.dependency_overrides = {}

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["output"] == {"ok": True}
