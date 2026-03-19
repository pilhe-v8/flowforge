# Tool Gateway Dispatch MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `POST /v1/tool-calls:invoke` execute tools synchronously (after JWT auth) via the existing `flowforge.tools.executor.ToolExecutor` and return a completed response.

**Architecture:** Add a dependency provider `get_tool_executor()` in the tool-gateway package. The invoke route depends on both `get_current_user` and `get_tool_executor`, calls `await executor.execute(...)`, and maps errors to HTTP status codes.

**Tech Stack:** FastAPI, pytest, existing `MCPToolClient` + `HTTPToolClient` + `ToolExecutor`.

---

### Task 1: Add dispatch tests (fake executor via dependency override)

**Files:**
- Test: `backend/tests/tool_gateway/test_dispatch.py`

**Step 1: Write the failing test**

Create `backend/tests/tool_gateway/test_dispatch.py`:

```python
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

    client = TestClient(app)
    resp = client.post(
        "/v1/tool-calls:invoke",
        json={"tool_uri": "mcp://example/tool", "inputs": {"q": "hi"}},
    )

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

    client = TestClient(app)
    resp = client.post(
        "/v1/tool-calls:invoke",
        json={"tool_uri": "ftp://nope", "inputs": {}},
    )

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

    client = TestClient(app)
    resp = client.post(
        "/v1/tool-calls:invoke",
        json={"tool_uri": "mcp://example/tool", "inputs": {}},
    )

    assert resp.status_code == 502
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q backend/tests/tool_gateway/test_dispatch.py`

Expected: FAIL (missing `get_tool_executor` and/or endpoint still returns 501).

---

### Task 2: Implement dispatch in the gateway endpoint

**Files:**
- Modify: `backend/flowforge/tool_gateway/api.py`

**Step 1: Implement minimal production code to pass tests**

In `backend/flowforge/tool_gateway/api.py`:

- Add a dependency provider:

```python
from functools import lru_cache
from flowforge.tools.executor import ToolExecutor
from flowforge.tools.mcp_client import MCPToolClient
from flowforge.tools.http_client import HTTPToolClient


@lru_cache
def get_tool_executor() -> ToolExecutor:
    return ToolExecutor(MCPToolClient(), HTTPToolClient())
```

- Update `invoke_tool_call` to:
  - Depend on `executor: ToolExecutor = Depends(get_tool_executor)`
  - Call `result = await executor.execute(body.tool_uri, body.inputs)`
  - Return `ToolCallInvokeResponse(status="completed", tool_call_id=str(uuid4()), output=result)`
  - `except ValueError as e: raise HTTPException(400, detail=str(e))`
  - `except Exception: raise HTTPException(502, detail="Tool execution failed")`

**Step 2: Run tests**

Run: `python3 -m pytest -q backend/tests/tool_gateway/test_dispatch.py`

Expected: PASS.

Run: `python3 -m pytest -q backend/tests/tool_gateway`

Expected: PASS.

**Step 3: Commit**

```bash
git add backend/flowforge/tool_gateway/api.py backend/tests/tool_gateway/test_dispatch.py
git commit -m "feat: dispatch tool calls via gateway"
```

---

### Task 3: Verify docker-compose behavior

**Files:**
- None

**Step 1: Run compose service**

Run: `docker compose up -d --build tool-gateway`

**Step 2: Verify health**

Run: `curl -s -o /dev/null -w "%{http_code}\\n" http://localhost:8010/health`

Expected: `200`.

**Step 3: Verify unauth invoke still fails closed**

Run:

```bash
curl -s -o /dev/null -w "%{http_code}\\n" \
  -X POST http://localhost:8010/v1/tool-calls:invoke \
  -H 'content-type: application/json' \
  -d '{"tool_uri":"mcp://example/tool","inputs":{"q":"hi"}}'
```

Expected: `401`.
