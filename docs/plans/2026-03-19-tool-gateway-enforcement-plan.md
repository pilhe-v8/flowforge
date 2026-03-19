# Tool Gateway Enforcement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Route all FlowForge tool invocations (including output actions like `log`) through the Tool Gateway via `POST /v1/tool-calls:invoke`, removing in-process direct tool execution.

**Architecture:** Replace `flowforge.tools.executor.ToolExecutor` routing (MCP/HTTP) with a gateway-backed implementation that calls the Tool Gateway using a service JWT. Update compiler/runtime call sites to use that executor and remove `log` bypass in `NodeFactory`.

**Tech Stack:** Python 3.12, FastAPI (gateway), httpx AsyncClient, pytest.

---

### Task 1: Add tool gateway settings

**Files:**
- Modify: `backend/flowforge/config.py`
- Test: `backend/tests/config/test_settings.py` (create if missing)

**Step 1: Write the failing test**

Create/extend settings tests to assert defaults and env overrides.

```python
def test_tool_gateway_settings_defaults(monkeypatch):
    monkeypatch.delenv("FLOWFORGE_TOOL_GATEWAY_URL", raising=False)
    monkeypatch.delenv("FLOWFORGE_TOOL_GATEWAY_JWT", raising=False)

    from flowforge.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.tool_gateway_url
    assert s.tool_gateway_url.startswith("http")
    assert s.tool_gateway_jwt in ("", None)


def test_tool_gateway_settings_env_override(monkeypatch):
    monkeypatch.setenv("FLOWFORGE_TOOL_GATEWAY_URL", "http://tool-gateway:8010")
    monkeypatch.setenv("FLOWFORGE_TOOL_GATEWAY_JWT", "jwt-token")

    from flowforge.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.tool_gateway_url == "http://tool-gateway:8010"
    assert s.tool_gateway_jwt == "jwt-token"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q backend/tests/config/test_settings.py`
Expected: FAIL because `tool_gateway_url` / `tool_gateway_jwt` do not exist.

**Step 3: Write minimal implementation**

In `backend/flowforge/config.py` add fields to `Settings` with defaults:

- `tool_gateway_url: str = "http://tool-gateway:8010"`
- `tool_gateway_jwt: str = ""`

Ensure env var names follow existing conventions (FlowForge prefix).

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q backend/tests/config/test_settings.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/flowforge/config.py backend/tests/config/test_settings.py
git commit -m "feat: add tool-gateway settings"
```

### Task 2: Implement a gateway tool client

**Files:**
- Create: `backend/flowforge/tools/gateway_client.py`
- Test: `backend/tests/tools/test_gateway_client.py`

**Step 1: Write the failing test**

Use `httpx.MockTransport` to assert request shape and headers.

```python
import httpx
import pytest


@pytest.mark.asyncio
async def test_gateway_client_posts_to_invoke_with_bearer_token():
    from flowforge.tools.gateway_client import ToolGatewayClient

    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        body = await request.aread()
        seen["body"] = body.decode("utf-8")
        return httpx.Response(
            200,
            json={"status": "completed", "tool_call_id": "t1", "output": {"ok": True}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://gw") as client:
        gw = ToolGatewayClient(base_url="http://gw", jwt_token="token", client=client)
        out = await gw.invoke("mcp://x/y", {"q": "hi"}, context={"actor": {"sub": "svc"}})

    assert out == {"ok": True}
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/v1/tool-calls:invoke")
    assert seen["auth"] == "Bearer token"
    assert "mcp://x/y" in seen["body"]
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q backend/tests/tools/test_gateway_client.py`
Expected: FAIL due to missing module/class.

**Step 3: Write minimal implementation**

Implement `ToolGatewayClient`:

- Constructor args: `base_url: str`, `jwt_token: str`, optional injected `httpx.AsyncClient`
- Method `async invoke(tool_uri: str, inputs: dict, context: dict | None = None) -> dict`
- Sends `Authorization: Bearer ...` header
- Parses Tool Gateway response JSON and returns `.output` (default `{}`)
- Raises on non-2xx with helpful message

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q backend/tests/tools/test_gateway_client.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/flowforge/tools/gateway_client.py backend/tests/tools/test_gateway_client.py
git commit -m "feat: add tool-gateway client"
```

### Task 3: Make ToolExecutor gateway-backed (fail-closed)

**Files:**
- Modify: `backend/flowforge/tools/executor.py`
- Modify: `backend/tests/tools/test_executor.py`

**Step 1: Write the failing test**

Update executor tests to assert it calls the gateway client.

```python
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_tool_executor_routes_via_gateway():
    from flowforge.tools.executor import ToolExecutor

    gw = AsyncMock()
    gw.invoke.return_value = {"ok": True}
    ex = ToolExecutor(gateway_client=gw)

    out = await ex.execute("http://example", {"a": 1})
    assert out == {"ok": True}
    gw.invoke.assert_awaited_once()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q backend/tests/tools/test_executor.py`
Expected: FAIL because constructor/signature differs.

**Step 3: Write minimal implementation**

Change `ToolExecutor` to:

- Accept `gateway_client` (preferred) OR construct one from settings.
- `execute()` calls `gateway_client.invoke(tool_uri, inputs, context=...)`.
- Fail-closed if no gateway URL/JWT configured.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q backend/tests/tools/test_executor.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/flowforge/tools/executor.py backend/tests/tools/test_executor.py
git commit -m "feat: route ToolExecutor via tool-gateway"
```

### Task 4: Route output actions (including log) via ToolExecutor

**Files:**
- Modify: `backend/flowforge/compiler/node_factory.py`
- Modify: `backend/tests/compiler/test_node_factory.py`

**Step 1: Write the failing test**

Update the existing test that asserts `log` does not call ToolExecutor.

```python
@pytest.mark.asyncio
async def test_output_action_log_routes_via_tool_executor_and_records_audit():
    from unittest.mock import AsyncMock

    from flowforge.compiler.node_factory import NodeFactory
    from flowforge.compiler.parser import StepDef

    tool_executor = AsyncMock()
    tool_executor.execute.return_value = {"ok": True}
    factory = NodeFactory(tool_executor=tool_executor)

    step = StepDef(
        id="out",
        name="Out",
        step_type="output",
        action_uri="log",
        input_mapping={"message": "hello"},
    )

    node_fn = factory.build_node(step)
    state = {"trigger": {}, "_audit_trail": []}
    result = await node_fn(state)

    tool_executor.execute.assert_awaited_once_with("log", {"message": "hello"})
    assert result["_audit_trail"][-1]["step_id"] == "out"
    assert result["_audit_trail"][-1]["type"] == "output"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q backend/tests/compiler/test_node_factory.py`
Expected: FAIL because current code bypasses.

**Step 3: Write minimal implementation**

In `NodeFactory._build_output_node`:

- Remove the `if step.action_uri == "log"` branch.
- Always call `await self.tool_executor.execute(step.action_uri, inputs)` if tool_executor exists.
- Decide what `state[step.id]` should store for output steps (either inputs, tool result, or both) and update tests.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q backend/tests/compiler/test_node_factory.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/flowforge/compiler/node_factory.py backend/tests/compiler/test_node_factory.py
git commit -m "feat: route output actions via ToolExecutor"
```

### Task 5: Wire worker runtime to construct ToolExecutor using gateway

**Files:**
- Modify: `backend/flowforge/worker/graph_cache.py`
- Test: `backend/tests/worker/test_graph_cache_runtime_deps.py` (create if missing)

**Step 1: Write the failing test**

Test that `_get_runtime_deps()` builds a ToolExecutor that is gateway-backed (and does not instantiate MCP/HTTP clients).

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q backend/tests/worker/test_graph_cache_runtime_deps.py`
Expected: FAIL.

**Step 3: Write minimal implementation**

Update `backend/flowforge/worker/graph_cache.py`:

- Remove `MCPToolClient()` / `HTTPToolClient()` construction.
- Construct `ToolExecutor()` with default gateway config or injected client.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q backend/tests/worker/test_graph_cache_runtime_deps.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/flowforge/worker/graph_cache.py backend/tests/worker/test_graph_cache_runtime_deps.py
git commit -m "refactor: build tool executor via gateway in worker"
```

### Task 6: Verification and smoke checks

**Files:**
- None

**Step 1: Run tool-gateway unit tests**

Run: `python3 -m pytest -q backend/tests/tool_gateway`
Expected: PASS.

**Step 2: Run backend unit tests for tool routing**

Run: `python3 -m pytest -q backend/tests/tools backend/tests/compiler`
Expected: PASS.

**Step 3: Run docker compose for gateway**

Run: `docker compose up -d --build tool-gateway`
Expected: container running.

**Step 4: Verify unauth gateway call fails closed**

Run:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8010/v1/tool-calls:invoke \
  -H 'content-type: application/json' \
  -d '{"tool_uri":"mcp://example/tool","inputs":{"q":"hi"}}'
```

Expected: `401`.
