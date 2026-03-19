import pytest


def test_log_tool_does_not_log_full_inputs(caplog):
    import logging

    from fastapi.testclient import TestClient

    from flowforge.tool_gateway.auth import get_current_user
    from flowforge.tool_gateway.main import app

    caplog.set_level(logging.INFO)

    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1"}
    try:
        client = TestClient(app)
        resp = client.post(
            "/v1/tool-calls:invoke",
            json={
                "tool_uri": "log",
                "inputs": {"message": "email=test@example.com secret=abc123", "other": "value"},
            },
        )
    finally:
        app.dependency_overrides = {}

    assert resp.status_code == 200
    assert "tool-gateway log tool" in caplog.text
    assert "test@example.com" not in caplog.text
    assert "abc123" not in caplog.text
    assert "value" not in caplog.text


def test_invoke_logs_exception_with_tool_uri_without_inputs(caplog):
    import logging

    from fastapi.testclient import TestClient

    from flowforge.tool_gateway.api import get_tool_executor
    from flowforge.tool_gateway.auth import get_current_user
    from flowforge.tool_gateway.main import app

    caplog.set_level(logging.INFO)

    class FakeExecutor:
        async def execute(self, tool_uri: str, inputs: dict, auth: dict | None = None) -> dict:
            raise RuntimeError("boom")

    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1"}
    app.dependency_overrides[get_tool_executor] = lambda: FakeExecutor()
    try:
        client = TestClient(app)
        resp = client.post(
            "/v1/tool-calls:invoke",
            json={"tool_uri": "mcp://example/tool", "inputs": {"secret": "abc123"}},
        )
    finally:
        app.dependency_overrides = {}

    assert resp.status_code == 502
    assert "tool-gateway invoke failed" in caplog.text
    assert "mcp://example/tool" in caplog.text
    assert "abc123" not in caplog.text


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
