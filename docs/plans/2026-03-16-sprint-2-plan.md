# Sprint 2 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix six known platform gaps: E2E automated test, node deletion, frontend error visibility, catalogue panel, node-type definitions panel, and observability (token tracking + execution detail UI).

**Architecture:** Six independent tracks. E2E fixes a backend bug in `node_factory.py` then adds a `tests/e2e/` pytest suite against the live Docker Compose stack. FE tracks add UI features to the React/Zustand frontend. OBS enriches the backend audit trail and surfaces it in the TestRunner modal. All tracks follow TDD: write the test first, then the code.

**Tech Stack:** Python 3.12, pytest, httpx, PyJWT, FastAPI, SQLAlchemy async, LangGraph, React 18, TypeScript, Zustand, React Flow v12, sonner (toast), Vite.

---

## Track E2E — End-to-End Automated Test + LLM Bug Fix

### Task E1: Fix agent node to call LLM without a profile loader

**Files:**
- Modify: `backend/flowforge/compiler/node_factory.py` (lines 88–113)
- Test: `backend/tests/compiler/test_node_factory.py`

**Context:**
`_build_agent_node` only calls the LLM when `self.profiles and self.llm` are both set.
`graph_cache.py` passes `profile_loader=None`, so in production the agent node always
returns empty strings and the LLM is never called. We fix this by adding a fallback direct-
chat path when `profile_loader` is `None`.

**Step 1: Write the failing test**

In `backend/tests/compiler/test_node_factory.py` add:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from flowforge.compiler.node_factory import NodeFactory
from flowforge.compiler.parser import StepDef


@pytest.mark.asyncio
async def test_agent_node_calls_llm_without_profile_loader():
    """Agent node must call LLM even when profile_loader is None."""
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = MagicMock(content="Hello from LLM")

    factory = NodeFactory(llm_client=mock_llm, profile_loader=None)
    step = StepDef(
        id="greet",
        name="Greet",
        step_type="agent",
        agent_slug="any-agent",
        context_mapping={"message": "hi"},
        output_vars=["reply"],
    )
    node_fn = factory.build_node(step)
    state = {"trigger": {"message": "hi"}}
    result = await node_fn(state)

    mock_llm.chat.assert_called_once()
    assert result["greet"]["reply"] == "Hello from LLM"
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/compiler/test_node_factory.py::test_agent_node_calls_llm_without_profile_loader -v
```
Expected: FAIL — `mock_llm.chat` not called, `result["greet"]["reply"]` is `""`.

**Step 3: Implement the fix**

In `backend/flowforge/compiler/node_factory.py`, replace `_build_agent_node` with:

```python
def _build_agent_node(self, step: StepDef) -> Callable:
    async def agent_node(state: dict) -> dict:
        from datetime import datetime, timezone
        started_at = datetime.now(timezone.utc)
        context = self._resolve_inputs(step.context_mapping, state)
        response_content = ""
        model = step.model or "default"

        if self.profiles and self.llm:
            profile = await self.profiles.load(step.agent_slug)
            from flowforge.agents.prompt_builder import PromptBuilder
            messages = PromptBuilder.build_messages(profile, context)
            model = step.model or getattr(profile, "default_model", None) or "default"
            response = await self.llm.chat(messages, model=model)
            response_content = response.content or ""
            input_tokens = response.input_tokens
            output_tokens = response.output_tokens
        elif self.llm:
            # No profile loader available — build a minimal direct-chat prompt
            context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": context_str or "Hello"},
            ]
            response = await self.llm.chat(messages, model=model)
            response_content = response.content or ""
            input_tokens = response.input_tokens
            output_tokens = response.output_tokens
        else:
            input_tokens = 0
            output_tokens = 0

        completed_at = datetime.now(timezone.utc)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        state[step.id] = {var: response_content for var in step.output_vars}
        state.setdefault("_audit_trail", []).append(
            {
                "step_id": step.id,
                "step_name": step.name,
                "step_type": "agent",
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_ms": duration_ms,
                "input": context,
                "output": state[step.id],
            }
        )
        return state

    return agent_node
```

**Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/compiler/test_node_factory.py::test_agent_node_calls_llm_without_profile_loader -v
```
Expected: PASS

**Step 5: Run full test suite to check for regressions**

```bash
cd backend && python -m pytest --tb=short -q
```
Expected: all 386 tests pass (plus the new one).

**Step 6: Commit**

```bash
git add backend/flowforge/compiler/node_factory.py backend/tests/compiler/test_node_factory.py
git commit -m "fix: agent node calls LLM directly when profile_loader is None, capture token counts in audit trail"
```

---

### Task E2: Create the E2E test infrastructure

**Files:**
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/e2e_workflow.yaml`
- Create: `tests/e2e/test_e2e_workflow.py`

**Context:**
These tests run against the **live Docker Compose stack** at `localhost:8000`. They are NOT
run as part of `cd backend && python -m pytest` (which runs unit/integration tests only).
They live at the repo root `tests/e2e/` and are run with `pytest tests/e2e/ -v`.

Prerequisites: Docker Compose stack must be running (`docker compose up -d`).

**Step 1: Create `tests/e2e/__init__.py`**

Empty file:
```python
```

**Step 2: Create `tests/e2e/e2e_workflow.yaml`**

```yaml
workflow:
  name: E2E Hello World
  slug: e2e-hello-world
  version: 1
  description: Minimal workflow for end-to-end testing — agent node only
  trigger:
    type: manual
    config: {}
    output: [message]
  steps:
    - id: greet
      name: Greet
      type: agent
      agent: e2e-test-agent
      context:
        message: "{{trigger.message}}"
      output: [reply]
      next: done
    - id: done
      name: Done
      type: output
      action: "http://localhost:1/noop"
      input:
        reply: "{{greet.reply}}"
```

**Step 3: Create `tests/e2e/conftest.py`**

```python
"""Fixtures for E2E tests against the live Docker Compose stack."""
import time
import uuid
import pytest
import requests
import jwt

BASE_URL = "http://localhost:8000"
JWT_SECRET = "dev-secret-change-in-production"
JWT_ALGORITHM = "HS256"


def mint_jwt(tenant_id: str, role: str = "user") -> str:
    payload = {
        "sub": f"e2e-{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant_id,
        "role": role,
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def mint_admin_jwt() -> str:
    """Admin JWT with a placeholder tenant_id (used only for tenant creation)."""
    payload = {
        "sub": "e2e-admin",
        "tenant_id": str(uuid.uuid4()),
        "role": "admin",
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def tenant_id(base_url):
    """Create a fresh tenant for this E2E session and return its ID."""
    admin_token = mint_admin_jwt()
    slug = f"e2e-tenant-{uuid.uuid4().hex[:8]}"
    resp = requests.post(
        f"{base_url}/api/v1/tenants",
        json={"name": f"E2E Tenant {slug}", "slug": slug},
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert resp.status_code == 201, f"Failed to create tenant: {resp.text}"
    data = resp.json()
    return data["id"]


@pytest.fixture(scope="session")
def auth_headers(tenant_id):
    """Bearer token headers scoped to the E2E tenant."""
    token = mint_jwt(tenant_id, role="admin")
    return {"Authorization": f"Bearer {token}"}
```

**Step 4: Create `tests/e2e/test_e2e_workflow.py`**

```python
"""End-to-end test: full request path from API through worker to LLM and back."""
import time
from pathlib import Path

import pytest
import requests

YAML_PATH = Path(__file__).parent / "e2e_workflow.yaml"
POLL_INTERVAL = 2  # seconds
POLL_TIMEOUT = 90  # seconds — allow time for LLM round-trip


def poll_until_complete(base_url, execution_id, auth_headers, timeout=POLL_TIMEOUT):
    """Poll GET /executions/{id} until status != queued/running."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{base_url}/api/v1/executions/{execution_id}",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200, f"Poll failed: {resp.text}"
        data = resp.json()
        if data["status"] not in ("queued", "running"):
            return data
        time.sleep(POLL_INTERVAL)
    pytest.fail(f"Execution {execution_id} did not complete within {timeout}s")


class TestE2EWorkflow:
    """Full stack test: API → DB → Redis → Worker → LangGraph → LiteLLM → response."""

    def test_create_workflow(self, base_url, auth_headers):
        yaml_def = YAML_PATH.read_text()
        resp = requests.post(
            f"{base_url}/api/v1/workflows",
            json={"name": "E2E Hello World", "yaml_definition": yaml_def},
            headers=auth_headers,
            timeout=10,
        )
        # 201 = created, 409 = already exists from a previous run (both are fine)
        assert resp.status_code in (201, 409), f"Unexpected status: {resp.text}"

    def test_deploy_workflow(self, base_url, auth_headers):
        resp = requests.post(
            f"{base_url}/api/v1/workflows/e2e-hello-world/deploy",
            json={},
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200, f"Deploy failed: {resp.text}"
        assert resp.json()["status"] == "active"

    def test_trigger_and_complete_execution(self, base_url, auth_headers):
        # Trigger
        resp = requests.post(
            f"{base_url}/api/v1/executions/trigger",
            json={
                "workflow_slug": "e2e-hello-world",
                "input_data": {"message": "Say hello in one sentence."},
            },
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 202, f"Trigger failed: {resp.text}"
        execution_id = resp.json()["execution_id"]
        assert execution_id

        # Poll until complete
        execution = poll_until_complete(base_url, execution_id, auth_headers)

        # Assert completed
        assert execution["status"] == "completed", (
            f"Execution ended with status={execution['status']}\n"
            f"Steps: {execution.get('steps')}"
        )

        # Assert agent step produced a non-empty LLM reply
        steps = {s["step_id"]: s for s in execution.get("steps", [])}
        assert "greet" in steps, f"Expected 'greet' step, got: {list(steps.keys())}"
        greet_output = steps["greet"].get("output") or {}
        reply = greet_output.get("reply", "")
        assert reply, (
            "Agent step 'greet' returned an empty reply — "
            "LLM was not called. Check node_factory.py and LiteLLM proxy."
        )
        print(f"\n✅ LLM reply: {reply[:120]}...")
```

**Step 5: Verify tests can be discovered**

```bash
pytest tests/e2e/ --collect-only
```
Expected: 3 tests collected from `test_e2e_workflow.py`.

**Step 6: Run the E2E tests** (Docker Compose must be running)

```bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin"
docker compose ps  # verify all services are up
pytest tests/e2e/ -v -s
```
Expected: all 3 tests PASS. The LLM reply is printed.

**Step 7: Commit**

```bash
git add tests/e2e/
git commit -m "feat: add E2E pytest suite proving full API→worker→LLM→DB round-trip"
```

---

## Track FE-1 — Node Deletion

### Task FE1-1: Wire keyboard Delete key and onNodesDelete

**Files:**
- Modify: `frontend/src/App.tsx`

**Context:**
`removeNode(id)` is already correct in the store. We just need to hook React Flow up to it.
`deleteKeyCode="Delete"` tells React Flow to emit remove changes on keyboard Delete/Backspace.
`onNodesDelete` is called by React Flow after it has already applied the remove change — we use
it to run our store action (for undo history and `isDirty` flag).

**Step 1: Add the handler and props to `App.tsx`**

Locate the section where `connectNodes` is destructured from `useWorkflowStore` (around line 30)
and add `removeNode`:

```tsx
const { nodes, edges, setNodes, setEdges, connectNodes, selectNode, removeNode } =
  useWorkflowStore(/* existing selector */);
```

Add the callback (after the existing `onConnect` callback):

```tsx
const onNodesDelete = useCallback(
  (deleted: Node[]) => {
    deleted.forEach(n => removeNode(n.id));
  },
  [removeNode],
);
```

Add two props to `<ReactFlow>`:

```tsx
<ReactFlow
  // ... existing props ...
  onNodesDelete={onNodesDelete}
  deleteKeyCode="Delete"
/>
```

**Step 2: Manual smoke test**

1. Open `http://localhost:5173`
2. Add a Tool node to the canvas
3. Click the node to select it (blue ring appears)
4. Press the `Delete` key
5. Expected: node disappears; Undo (Ctrl+Z / toolbar) restores it

**Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire keyboard Delete key and onNodesDelete to store removeNode action"
```

---

### Task FE1-2: Add × delete button to each node component

**Files:**
- Modify: `frontend/src/components/Nodes/TriggerNode.tsx`
- Modify: `frontend/src/components/Nodes/ToolNode.tsx`
- Modify: `frontend/src/components/Nodes/AgentNode.tsx`
- Modify: `frontend/src/components/Nodes/RouterNode.tsx`
- Modify: `frontend/src/components/Nodes/GateNode.tsx`
- Modify: `frontend/src/components/Nodes/OutputNode.tsx`

**Context:**
Each node component receives `selected` as a prop from React Flow. When selected, show a
small `×` button in the top-right corner. The button calls `removeNode` from the store.

**Step 1: Add the delete button pattern to each node**

The pattern is identical for all 6 files. Example for `AgentNode.tsx`:

Find the outer wrapper div (the one with `border rounded-lg shadow-sm ...`) and add inside it,
as the first child:

```tsx
import { useWorkflowStore } from '../../stores/workflowStore';

// Inside the component, before the return:
const removeNode = useWorkflowStore(s => s.removeNode);

// Inside the JSX, as the first child of the card wrapper div:
{selected && (
  <button
    onClick={e => { e.stopPropagation(); removeNode(id); }}
    className="absolute -top-2 -right-2 z-10 w-5 h-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center hover:bg-red-600 shadow"
    title="Delete node"
  >
    ×
  </button>
)}
```

The outer wrapper div must have `relative` in its className (add it if not present).

Repeat this pattern in all 6 node files.

**Step 2: Manual smoke test**

1. Add two nodes to the canvas
2. Connect them with an edge
3. Click to select node 1 — a red `×` badge appears in the top-right corner
4. Click the `×` — node 1 and its connected edge disappear
5. Undo restores both

**Step 3: Commit**

```bash
git add frontend/src/components/Nodes/
git commit -m "feat: add delete (×) button to selected node cards"
```

---

### Task FE1-3: Delete button in Properties Panel footer

**Files:**
- Modify: `frontend/src/components/Layout/PropertiesPanel.tsx` (or equivalent panel router file)

**Context:**
The right-side Properties Panel renders different sub-panels based on the selected node type.
Add a "Delete node" button at the bottom, visible only when a node is selected.

**Step 1: Find the Properties Panel container**

Open `frontend/src/components/Layout/PropertiesPanel.tsx`. It likely contains a switch/if on
`selectedNodeId` to choose which panel to render. Find the outer wrapper.

**Step 2: Add the delete button at the bottom of the panel**

```tsx
const removeNode = useWorkflowStore(s => s.removeNode);
const selectedNodeId = useWorkflowStore(s => s.selectedNodeId);

// At the bottom of the rendered panel content, before the closing wrapper div:
{selectedNodeId && (
  <div className="border-t border-gray-200 p-3 mt-2">
    <button
      onClick={() => removeNode(selectedNodeId)}
      className="w-full text-sm text-red-600 hover:text-red-800 hover:bg-red-50 rounded px-3 py-1.5 border border-red-200"
    >
      Delete node
    </button>
  </div>
)}
```

**Step 3: Manual smoke test**

1. Select any node — Properties Panel appears on the right
2. Scroll to the bottom of the panel — "Delete node" button is visible
3. Click it — node is removed, panel closes

**Step 4: Commit**

```bash
git add frontend/src/components/Layout/PropertiesPanel.tsx
git commit -m "feat: add Delete node button at Properties Panel footer"
```

---

## Track FE-2 — Frontend Error Visibility + Auth Dev Bypass

### Task FE2-1: Add sonner toast library

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.tsx`

**Step 1: Install sonner**

```bash
cd frontend && npm install sonner
```

**Step 2: Add `<Toaster>` to `main.tsx`**

```tsx
import { Toaster } from 'sonner';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Toaster position="top-right" richColors />
    <App />
  </React.StrictMode>
);
```

**Step 3: Verify build**

```bash
cd frontend && npm run build
```
Expected: build succeeds with no errors.

**Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.tsx
git commit -m "feat: add sonner toast library"
```

---

### Task FE2-2: Add Axios response interceptor

**Files:**
- Modify: `frontend/src/api/client.ts`

**Step 1: Replace the current `client.ts`**

```typescript
import axios from 'axios';
import { toast } from 'sonner';

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('flowforge_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Surface API errors as toasts
apiClient.interceptors.response.use(
  response => response,
  error => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    if (status === 401) {
      localStorage.removeItem('flowforge_token');
      toast.error('Session expired — please reload the page.');
    } else if (status === 403) {
      toast.error('Permission denied.');
    } else if (status === 404) {
      toast.error(typeof detail === 'string' ? detail : 'Resource not found.');
    } else if (status === 409) {
      toast.error(typeof detail === 'string' ? detail : 'Conflict — resource already exists.');
    } else if (status === 422) {
      const msg = Array.isArray(detail)
        ? detail.map((d: { msg: string }) => d.msg).join('; ')
        : typeof detail === 'string'
          ? detail
          : 'Validation error.';
      toast.error(msg);
    } else if (status >= 500) {
      toast.error('Server error — check the logs.');
    } else {
      toast.error(typeof detail === 'string' ? detail : `Request failed (${status}).`);
    }

    return Promise.reject(error);
  }
);
```

**Step 2: Verify dev server builds and errors are visible**

Open DevTools Network tab. Hard-reload `http://localhost:5173`. You should see two 401 requests
to `/api/v1/tools/catalogue` and `/api/v1/agents` — and two red toast notifications should
briefly appear in the top-right corner of the page.

**Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add Axios response interceptor to surface API errors as toasts"
```

---

### Task FE2-3: Dev auth bypass — auto-mint dev JWT

**Files:**
- Create: `scripts/mint_dev_token.py`
- Modify: `frontend/src/App.tsx`

**Context:**
There is no login page. For local development, we auto-mint a JWT and store it in localStorage
on app startup. The token is signed with `dev-secret-change-in-production` (the default
`FLOWFORGE_JWT_SECRET`). The `tenant_id` must be a real tenant that exists in the DB.

We'll hardcode a well-known dev tenant ID created by a seed script.

**Step 1: Create `scripts/mint_dev_token.py`**

```python
#!/usr/bin/env python3
"""
Mints a dev JWT for local development.

Usage:
    python scripts/mint_dev_token.py

Prints the JWT to stdout. Copy it into localStorage manually, or rely on
the frontend's auto-bootstrap (App.tsx reads VITE_DEV_JWT env var).
"""
import sys
import time
import uuid
import jwt

SECRET = "dev-secret-change-in-production"
ALGORITHM = "HS256"


def main():
    # Use a fixed UUID so it stays stable across runs
    tenant_id = "00000000-0000-0000-0000-000000000001"
    payload = {
        "sub": "dev-user",
        "tenant_id": tenant_id,
        "role": "admin",
        "exp": int(time.time()) + 86400 * 30,  # 30 days
    }
    token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
    print(token)


if __name__ == "__main__":
    main()
```

**Step 2: Create the dev tenant in the DB**

Add a DB migration or seed script. The simplest approach for local dev is a one-time curl:

```bash
# First, mint a bootstrap admin token with the fixed tenant_id
python scripts/mint_dev_token.py
# Copy the token, then:
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"name": "Dev Tenant", "slug": "dev"}'
```

This creates the dev tenant with ID `00000000-0000-0000-0000-000000000001` (we'll make the tenant creation accept an explicit ID in the next step, or just let the backend generate one and use that ID instead — see note below).

> **Note:** Since `tenants.py` generates a random UUID, we cannot force a specific ID via the API. Instead, run:
> ```bash
> docker compose exec postgres psql -U flowforge -d flowforge -c \
>   "INSERT INTO tenants (id, name, slug, config) VALUES ('00000000-0000-0000-0000-000000000001', 'Dev Tenant', 'dev', '{}') ON CONFLICT DO NOTHING;"
> ```

**Step 3: Add auto-bootstrap to `App.tsx`**

At the top of the `App` component function body, before the `useEffect`:

```tsx
// Dev auth bootstrap — auto-set JWT if not present (local dev only)
useEffect(() => {
  if (!localStorage.getItem('flowforge_token')) {
    const devToken = import.meta.env.VITE_DEV_JWT as string | undefined;
    if (devToken) {
      localStorage.setItem('flowforge_token', devToken);
      window.location.reload();  // reload so all pending requests retry with the token
    }
  }
}, []);
```

**Step 4: Add `VITE_DEV_JWT` to `.env.local`**

```bash
cd frontend
python ../scripts/mint_dev_token.py  # prints the token
echo "VITE_DEV_JWT=<paste token here>" > .env.local
```

Add `.env.local` to `.gitignore` (it already is by default in Vite projects — verify):

```bash
grep .env.local .gitignore || echo ".env.local" >> .gitignore
```

**Step 5: Create dev tenant in DB (one-time setup)**

```bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin"
docker compose exec postgres psql -U flowforge -d flowforge -c \
  "INSERT INTO tenants (id, name, slug, config) VALUES ('00000000-0000-0000-0000-000000000001', 'Dev Tenant', 'dev', '{}') ON CONFLICT DO NOTHING;"
```

**Step 6: Verify**

Hard-reload `http://localhost:5173`. The 401 toasts should be gone. The catalogue and agents
API calls should succeed (200 OK visible in DevTools Network tab).

**Step 7: Commit**

```bash
git add scripts/mint_dev_token.py frontend/src/App.tsx frontend/.gitignore
git commit -m "feat: add dev JWT auto-bootstrap and seed script for local development"
```

---

### Task FE2-4: Surface stored catalogue errors + add ErrorBoundary

**Files:**
- Create: `frontend/src/components/shared/ErrorBoundary.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/stores/workflowStore.ts`

**Step 1: Create `ErrorBoundary.tsx`**

```tsx
import { Component, ErrorInfo, ReactNode } from 'react';

interface Props { children: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-screen bg-gray-50">
          <div className="text-center p-8 bg-white rounded-lg shadow max-w-md">
            <h1 className="text-xl font-semibold text-red-600 mb-2">Something went wrong</h1>
            <pre className="text-sm text-gray-600 bg-gray-100 p-3 rounded text-left overflow-auto">
              {this.state.error?.message}
            </pre>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
```

**Step 2: Wrap `<App>` in `main.tsx`**

```tsx
import { ErrorBoundary } from './components/shared/ErrorBoundary';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <Toaster position="top-right" richColors />
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
```

**Step 3: Surface catalogue error in `App.tsx`**

In the `useEffect` that calls `fetchCatalogue()` and `fetchAgentsAction()`, import and use `toast`:

```tsx
import { toast } from 'sonner';
// ...
const catalogueError = useToolCatalogueStore(s => s.error);

useEffect(() => {
  if (catalogueError) toast.error(`Catalogue: ${catalogueError}`);
}, [catalogueError]);
```

**Step 4: Add try/catch to `workflowStore.save()` and `deploy()`**

In `workflowStore.ts`, find the `save` and `deploy` actions and wrap their API calls:

```ts
// save action — replace console.error pattern
save: async () => {
  try {
    // ... existing save logic ...
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    // toast is called from the response interceptor; just re-throw
    throw e;
  }
},
```

Actually the interceptor already toasts on error — the key fix is removing the silent
`.catch(console.error)` in `Toolbar.tsx` and replacing it with a no-op (the interceptor handles it).

In `Toolbar.tsx`, find:
```ts
onClick={() => save().catch(console.error)}
```
Replace with:
```ts
onClick={() => { save().catch(() => {}); }}  // interceptor already toasted
```
Same for deploy.

**Step 5: Commit**

```bash
git add frontend/src/components/shared/ErrorBoundary.tsx frontend/src/main.tsx \
        frontend/src/App.tsx frontend/src/stores/workflowStore.ts \
        frontend/src/components/Layout/Toolbar.tsx
git commit -m "feat: add ErrorBoundary, surface catalogue errors and fix silent save/deploy failures"
```

---

## Track FE-3 — Catalogue Panel

### Task FE3-1: Refactor NodePalette to a tabbed panel with catalogue tab

**Files:**
- Modify: `frontend/src/components/Layout/NodePalette.tsx`
- Modify: `frontend/src/stores/workflowStore.ts` (ensure `updateNodeData` is accessible)

**Context:**
Replace the single-list NodePalette with a two-tab layout:
- Tab "Node Types" — the existing 6 generic node buttons (unchanged behaviour)
- Tab "Catalogue" — searchable list of tools and agents from `toolCatalogueStore`

Clicking "+ Add" on a catalogue item calls `addNode(type, pos)` then immediately
`updateNodeData(id, { toolUri: tool.uri, toolName: tool.name })` to pre-configure it.

**Step 1: Refactor `NodePalette.tsx`**

```tsx
import { useState } from 'react';
import { useWorkflowStore } from '../../stores/workflowStore';
import { useToolCatalogueStore } from '../../stores/toolCatalogueStore';
import type { NodeType } from '../../types';

const NODE_TYPES = [
  { type: 'trigger' as NodeType, label: 'Trigger', icon: '⚡', description: 'Workflow entry point' },
  { type: 'tool'    as NodeType, label: 'Tool',    icon: '🔧', description: 'Call an external tool or MCP server' },
  { type: 'agent'   as NodeType, label: 'Agent',   icon: '🧠', description: 'Run an LLM-powered agent' },
  { type: 'router'  as NodeType, label: 'Router',  icon: '◆',  description: 'Branch on a value' },
  { type: 'gate'    as NodeType, label: 'Gate',    icon: '🛡',  description: 'Apply conditional rules' },
  { type: 'output'  as NodeType, label: 'Output',  icon: '📤', description: 'Send a result or call an action' },
];

export function NodePalette() {
  const [tab, setTab] = useState<'types' | 'catalogue'>('types');
  const [search, setSearch] = useState('');
  const addNode = useWorkflowStore(s => s.addNode);
  const updateNodeData = useWorkflowStore(s => s.updateNodeData);
  const nodes = useWorkflowStore(s => s.nodes);
  const tools = useToolCatalogueStore(s => s.tools);
  const agents = useToolCatalogueStore(s => s.agents);

  const nextPosition = () => {
    const offset = (nodes.length % 10) * 30;
    return { x: 250 + offset, y: 100 + offset };
  };

  const addToolFromCatalogue = (tool: { uri: string; name: string; slug: string }) => {
    const pos = nextPosition();
    addNode('tool', pos);
    const newId = `tool-${Date.now()}`;  // matches the id pattern in addNode
    // Use a short delay to ensure node is in state before updateNodeData
    setTimeout(() => {
      const latestNodes = useWorkflowStore.getState().nodes;
      const added = latestNodes[latestNodes.length - 1];
      if (added) updateNodeData(added.id, { toolUri: tool.uri, toolName: tool.name, label: tool.name });
    }, 0);
  };

  const addAgentFromCatalogue = (agent: { slug: string; name: string }) => {
    const pos = nextPosition();
    addNode('agent', pos);
    setTimeout(() => {
      const latestNodes = useWorkflowStore.getState().nodes;
      const added = latestNodes[latestNodes.length - 1];
      if (added) updateNodeData(added.id, { agentSlug: agent.slug, label: agent.name });
    }, 0);
  };

  const filteredTools = tools.filter(t =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    t.description?.toLowerCase().includes(search.toLowerCase())
  );
  const filteredAgents = agents.filter(a =>
    a.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="w-56 bg-white border-r border-gray-200 flex flex-col h-full">
      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {(['types', 'catalogue'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 text-xs font-medium capitalize ${
              tab === t
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'types' ? 'Node Types' : 'Catalogue'}
          </button>
        ))}
      </div>

      {tab === 'types' && (
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {NODE_TYPES.map(({ type, label, icon }) => (
            <button
              key={type}
              onClick={() => addNode(type, nextPosition())}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded hover:bg-gray-50 text-left"
            >
              <span>{icon}</span>
              <span>{label}</span>
            </button>
          ))}
        </div>
      )}

      {tab === 'catalogue' && (
        <div className="flex-1 overflow-y-auto flex flex-col">
          <div className="p-2">
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
            />
          </div>
          <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-3">
            {filteredTools.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide py-1">Tools</p>
                {filteredTools.map(tool => (
                  <div key={tool.slug} className="flex items-start justify-between gap-1 py-1">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-800 truncate">🔧 {tool.name}</p>
                      {tool.description && (
                        <p className="text-xs text-gray-400 truncate">{tool.description}</p>
                      )}
                    </div>
                    <button
                      onClick={() => addToolFromCatalogue(tool)}
                      className="shrink-0 text-xs px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
                    >
                      +
                    </button>
                  </div>
                ))}
              </div>
            )}
            {filteredAgents.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide py-1">Agents</p>
                {filteredAgents.map(agent => (
                  <div key={agent.slug} className="flex items-center justify-between gap-1 py-1">
                    <p className="text-xs font-medium text-gray-800 truncate">🧠 {agent.name}</p>
                    <button
                      onClick={() => addAgentFromCatalogue(agent)}
                      className="shrink-0 text-xs px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
                    >
                      +
                    </button>
                  </div>
                ))}
              </div>
            )}
            {filteredTools.length === 0 && filteredAgents.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-4">
                {tools.length === 0 && agents.length === 0
                  ? 'No tools or agents registered yet.'
                  : 'No results match your search.'}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Manual smoke test**

1. Open `http://localhost:5173`
2. Click "Catalogue" tab — tools and agents from the backend appear
3. Type in the search box — list filters live
4. Click `+` next to a tool — a pre-configured Tool node appears on the canvas

**Step 3: Commit**

```bash
git add frontend/src/components/Layout/NodePalette.tsx
git commit -m "feat: add Catalogue tab to NodePalette showing registered tools and agents"
```

---

## Track FE-4 — Node-Type Definitions Panel

### Task FE4-1: Create static node definitions and collapsible help drawer

**Files:**
- Create: `frontend/src/components/shared/NodeDefinitions.ts`
- Create: `frontend/src/components/shared/DefinitionDrawer.tsx`
- Modify: `frontend/src/components/Layout/PropertiesPanel.tsx`

**Step 1: Create `NodeDefinitions.ts`**

```typescript
export interface FieldDef {
  name: string;
  description: string;
  example: string;
  required: boolean;
}

export interface NodeDef {
  type: string;
  icon: string;
  title: string;
  summary: string;
  fields: FieldDef[];
}

export const NODE_DEFINITIONS: Record<string, NodeDef> = {
  trigger: {
    type: 'trigger',
    icon: '⚡',
    title: 'Trigger',
    summary: 'The workflow entry point. Defines what event starts the workflow and what data it provides to subsequent steps.',
    fields: [
      { name: 'type', description: 'The event type that starts this workflow', example: 'manual | webhook | email_received | schedule', required: true },
      { name: 'output', description: 'Variable names this trigger makes available to later steps', example: '[message, sender, body]', required: true },
    ],
  },
  tool: {
    type: 'tool',
    icon: '🔧',
    title: 'Tool',
    summary: 'Calls an external tool — either an MCP server (mcp://) or an HTTP endpoint (http://). The tool runs synchronously and its output becomes available to later steps.',
    fields: [
      { name: 'tool', description: 'URI of the tool to call', example: 'mcp://crm-service:9000/customer-lookup', required: true },
      { name: 'input.*', description: 'Variables to pass to the tool. Use {{step_id.var}} to reference previous step outputs.', example: 'email: "{{trigger.sender}}"', required: false },
      { name: 'output', description: 'Variable names returned by the tool', example: '[customer_id, name, tier]', required: true },
      { name: 'fallback', description: 'If the tool result fails a condition, run an agent instead', example: 'when: "confidence < 0.85"', required: false },
    ],
  },
  agent: {
    type: 'agent',
    icon: '🧠',
    title: 'Agent',
    summary: 'Runs an LLM-powered agent from your agent profile library. The agent receives context variables and returns one or more output variables containing the LLM\'s response.',
    fields: [
      { name: 'agent', description: 'Slug of the agent profile to use', example: 'reply-drafter', required: true },
      { name: 'model', description: 'Override the agent\'s default LLM model', example: 'gpt-4o-mini | mistral-large-latest', required: false },
      { name: 'context.*', description: 'Variables passed as context to the LLM prompt', example: 'message: "{{trigger.body}}"', required: false },
      { name: 'output', description: 'Variable names the agent produces', example: '[reply, summary]', required: true },
    ],
  },
  router: {
    type: 'router',
    icon: '◆',
    title: 'Router',
    summary: 'Branches the workflow based on the value of a variable. Routes traffic to different steps based on exact string matches, with a default fallback.',
    fields: [
      { name: 'on', description: 'The variable value to switch on', example: '{{classify.intent}}', required: true },
      { name: 'routes.*', description: 'Map of value → next step ID', example: 'billing: fetch_invoice', required: true },
      { name: 'default', description: 'Step to go to if no route matches', example: 'general_response', required: false },
    ],
  },
  gate: {
    type: 'gate',
    icon: '🛡',
    title: 'Gate',
    summary: 'Evaluates a list of boolean rules against the current workflow state. Routes to the first matching rule\'s target step, or to the default if none match.',
    fields: [
      { name: 'rules[].if', description: 'Boolean Python expression evaluated against current state', example: 'len(draft_response) < 20', required: true },
      { name: 'rules[].then', description: 'Step ID to route to when this rule matches', example: 'draft_reply', required: true },
      { name: 'rules[].label', description: 'Human-readable label for this rule', example: 'Response too short', required: false },
      { name: 'default', description: 'Step ID if no rules match', example: 'send_reply', required: true },
    ],
  },
  output: {
    type: 'output',
    icon: '📤',
    title: 'Output',
    summary: 'The workflow terminal node. Calls an external action (MCP tool or HTTP endpoint) to deliver the final result — for example sending an email or creating a ticket.',
    fields: [
      { name: 'action', description: 'URI of the action to execute', example: 'mcp://email-service:9006/send', required: true },
      { name: 'input.*', description: 'Data to pass to the action', example: 'to: "{{trigger.sender}}"', required: false },
    ],
  },
};
```

**Step 2: Create `DefinitionDrawer.tsx`**

```tsx
import { useState } from 'react';
import { NODE_DEFINITIONS } from './NodeDefinitions';

interface Props {
  nodeType: string;
}

export function DefinitionDrawer({ nodeType }: Props) {
  const [open, setOpen] = useState(false);
  const def = NODE_DEFINITIONS[nodeType];
  if (!def) return null;

  return (
    <div className="border-t border-gray-200">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-50"
      >
        <span>? What is a {def.title}?</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-2">
          <p className="text-xs text-gray-600">{def.summary}</p>
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="text-left text-gray-400">
                <th className="pb-1 font-medium">Field</th>
                <th className="pb-1 font-medium">Description</th>
              </tr>
            </thead>
            <tbody>
              {def.fields.map(field => (
                <tr key={field.name} className="border-t border-gray-100">
                  <td className="py-1 pr-2 font-mono text-blue-700 whitespace-nowrap">
                    {field.name}
                    {field.required && <span className="text-red-500 ml-0.5">*</span>}
                  </td>
                  <td className="py-1 text-gray-600">
                    <div>{field.description}</div>
                    <div className="text-gray-400 font-mono">{field.example}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

**Step 3: Embed `<DefinitionDrawer>` in the Properties Panel**

In `PropertiesPanel.tsx`, find where the selected node type is determined (it reads from `nodes`
and `selectedNodeId`). After the sub-panel content and before the delete button footer, add:

```tsx
import { DefinitionDrawer } from '../shared/DefinitionDrawer';

// After rendering the type-specific panel:
{selectedNode && <DefinitionDrawer nodeType={selectedNode.type} />}
```

**Step 4: Manual smoke test**

1. Select any node — Properties Panel opens
2. At the bottom, below all fields, see "? What is an Agent?" (or the relevant type)
3. Click it — definition expands with summary and field table
4. Click again — collapses

**Step 5: Commit**

```bash
git add frontend/src/components/shared/NodeDefinitions.ts \
        frontend/src/components/shared/DefinitionDrawer.tsx \
        frontend/src/components/Layout/PropertiesPanel.tsx
git commit -m "feat: add collapsible node-type definition drawer to Properties Panel"
```

---

## Track OBS — Observability

### Task OBS-1: Write token data to audit trail and TokenUsage table

**Files:**
- Modify: `backend/flowforge/compiler/node_factory.py` (already done in Task E1)
- Modify: `backend/flowforge/worker/consumer.py`
- Test: `backend/tests/worker/test_consumer.py`

**Context:**
Task E1 already adds `input_tokens`, `output_tokens`, `started_at`, `completed_at`, and
`duration_ms` to the `_audit_trail`. Now we need `AuditLog.write()` to:
1. Insert `TokenUsage` rows for any trail entry that has token data
2. Set `execution.started_at` and `execution.duration_ms` from the trail

**Step 1: Write the failing test**

In `backend/tests/worker/test_consumer.py`, add:

```python
@pytest.mark.asyncio
async def test_audit_log_writes_token_usage(db_session):
    """AuditLog.write() must insert TokenUsage rows when audit trail has token data."""
    from flowforge.worker.consumer import AuditLog, MessageEnvelope
    from flowforge.worker.executor import ExecutionResult
    from flowforge.models import TokenUsage, Execution
    import uuid
    from datetime import datetime

    tenant_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    envelope = MessageEnvelope(
        session_id=str(uuid.uuid4()),
        workflow_slug="test-wf",
        tenant_id=tenant_id,
        input_data={},
        execution_id=execution_id,
    )
    result = ExecutionResult(
        session_id=envelope.session_id,
        final_state={},
        steps_executed=[
            {
                "step_id": "greet",
                "step_name": "Greet",
                "step_type": "agent",
                "status": "completed",
                "model": "mistral-large-latest",
                "input_tokens": 42,
                "output_tokens": 17,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
                "duration_ms": 1234,
                "input_data": {},
                "output_data": {},
            }
        ],
    )
    await AuditLog.write(envelope, result, workflow_version=1)

    # Assert TokenUsage row was created
    from sqlalchemy import select
    rows = (await db_session.execute(
        select(TokenUsage).where(TokenUsage.execution_id == uuid.UUID(execution_id))
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].input_tokens == 42
    assert rows[0].output_tokens == 17
    assert rows[0].model == "mistral-large-latest"
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/worker/test_consumer.py::test_audit_log_writes_token_usage -v
```
Expected: FAIL — `TokenUsage` rows not created.

**Step 3: Update `AuditLog.write()` in `consumer.py`**

Import `TokenUsage` at the top:
```python
from flowforge.models import Execution as ExecutionModel, ExecutionStep, TokenUsage
```

In `AuditLog.write()`, after inserting `ExecutionStep` rows, add:

```python
# Write TokenUsage rows for agent steps that captured token data
for step_entry in result.steps_executed:
    if not isinstance(step_entry, dict):
        continue
    input_tokens = step_entry.get("input_tokens")
    output_tokens = step_entry.get("output_tokens")
    if input_tokens is not None and output_tokens is not None:
        await db.execute(
            pg_insert(TokenUsage).values(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(envelope.tenant_id),
                execution_id=execution_id,
                step_id=step_entry.get("step_id", "unknown"),
                model=step_entry.get("model", "unknown"),
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                cost_usd=None,  # computed at query time
            ).on_conflict_do_nothing()
        )

# Set execution timing from audit trail
starts = [e["started_at"] for e in result.steps_executed if isinstance(e, dict) and "started_at" in e]
ends = [e["completed_at"] for e in result.steps_executed if isinstance(e, dict) and "completed_at" in e]
if starts and ends:
    first_start = min(starts)
    last_end = max(ends)
    from datetime import datetime
    t0 = datetime.fromisoformat(first_start)
    t1 = datetime.fromisoformat(last_end)
    duration_ms = int((t1 - t0).total_seconds() * 1000)
    await db.execute(
        pg_insert(ExecutionModel).values(
            id=execution_id,
            tenant_id=envelope.tenant_id,
            session_id=envelope.session_id,
            workflow_slug=envelope.workflow_slug,
            workflow_version=workflow_version,
            status="completed",
            input_data=envelope.input_data,
            output_data=result.final_state,
            started_at=t0,
            completed_at=t1,
            duration_ms=duration_ms,
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={
                "status": "completed",
                "output_data": result.final_state,
                "started_at": t0,
                "completed_at": t1,
                "duration_ms": duration_ms,
            }
        )
    )
```

**Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/worker/test_consumer.py::test_audit_log_writes_token_usage -v
```
Expected: PASS

**Step 5: Run full test suite**

```bash
cd backend && python -m pytest --tb=short -q
```

**Step 6: Commit**

```bash
git add backend/flowforge/worker/consumer.py backend/tests/worker/test_consumer.py
git commit -m "feat: write TokenUsage rows and execution timing from audit trail in AuditLog"
```

---

### Task OBS-2: Enrich GET /executions/{id} response

**Files:**
- Modify: `backend/flowforge/api/executions.py`
- Test: `backend/tests/api/test_executions.py`

**Step 1: Write the failing test**

In `backend/tests/api/test_executions.py`, add:

```python
def test_get_execution_includes_enriched_fields(client, execution_with_steps):
    """GET /executions/{id} must include model, tokens, duration per step."""
    resp = client.get(f"/api/v1/executions/{execution_with_steps.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "queued_at" in data
    assert "duration_ms" in data
    assert "workflow_slug" in data
    step = data["steps"][0]
    assert "step_name" in step
    assert "model" in step
    assert "input_tokens" in step
    assert "output_tokens" in step
    assert "duration_ms" in step
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/api/test_executions.py::test_get_execution_includes_enriched_fields -v
```

**Step 3: Update `get_execution` in `executions.py`**

Replace the return dict in `get_execution`:

```python
# Compute token totals
from sqlalchemy import select as sa_select
from flowforge.models import TokenUsage

token_rows = (await db.execute(
    sa_select(TokenUsage).where(TokenUsage.execution_id == exec_uuid)
)).scalars().all()

total_input = sum(t.input_tokens for t in token_rows)
total_output = sum(t.output_tokens for t in token_rows)

# Simple cost estimates (per 1K tokens)
COST_TABLE = {
    "mistral-large-latest": {"input": 0.003, "output": 0.009},
    "default":              {"input": 0.003, "output": 0.009},
    "gpt-4o":               {"input": 0.005, "output": 0.015},
    "gpt-4o-mini":          {"input": 0.00015, "output": 0.0006},
    "azure-fallback":       {"input": 0.005, "output": 0.015},
}
estimated_cost = sum(
    t.input_tokens / 1000 * COST_TABLE.get(t.model, {"input": 0.003})["input"] +
    t.output_tokens / 1000 * COST_TABLE.get(t.model, {"output": 0.009})["output"]
    for t in token_rows
)

# Order steps by started_at
steps_stmt = (
    select(ExecutionStep)
    .where(ExecutionStep.execution_id == exec_uuid)
    .order_by(ExecutionStep.started_at.asc().nullsfirst())
)
steps = (await db.execute(steps_stmt)).scalars().all()

return {
    "execution_id": str(execution.id),
    "workflow_slug": execution.workflow_slug,
    "status": execution.status,
    "queued_at": execution.queued_at.isoformat() if execution.queued_at else None,
    "started_at": execution.started_at.isoformat() if execution.started_at else None,
    "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
    "duration_ms": execution.duration_ms,
    "input_data": execution.input_data,
    "output_data": execution.output_data,
    "total_input_tokens": total_input,
    "total_output_tokens": total_output,
    "estimated_cost_usd": round(estimated_cost, 6),
    "steps": [
        {
            "step_id": s.step_id,
            "step_name": s.step_name,
            "type": s.step_type,
            "status": s.status,
            "model": s.step_metadata.get("model") if s.step_metadata else None,
            "input_tokens": s.step_metadata.get("input_tokens") if s.step_metadata else None,
            "output_tokens": s.step_metadata.get("output_tokens") if s.step_metadata else None,
            "duration_ms": s.duration_ms,
            "input": s.input_data,
            "output": s.output_data,
        }
        for s in steps
    ],
}
```

> **Note:** `step_metadata` JSONB is already on the `ExecutionStep` model. We need to store model/tokens there. Update `AuditLog.write()` in Task OBS-1 to also set `step_metadata={"model": ..., "input_tokens": ..., "output_tokens": ...}` on the `ExecutionStep` insert.

**Step 4: Run tests**

```bash
cd backend && python -m pytest tests/api/test_executions.py -v
cd backend && python -m pytest --tb=short -q
```

**Step 5: Commit**

```bash
git add backend/flowforge/api/executions.py backend/tests/api/test_executions.py
git commit -m "feat: enrich GET /executions/{id} with tokens, cost, timing, and workflow_slug"
```

---

### Task OBS-3: Extend TestRunner to show execution detail

**Files:**
- Modify: `frontend/src/components/TestRunner.tsx`
- Modify: `frontend/src/api/executions.ts`
- Modify: `frontend/src/types/index.ts`

**Step 1: Update TypeScript types in `types/index.ts`**

Find the `Execution` and `ExecutionStep` interfaces and replace/update:

```typescript
export interface ExecutionStep {
  step_id: string;
  step_name: string;
  type: string;
  status: string;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  duration_ms: number | null;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
}

export interface ExecutionDetail {
  execution_id: string;
  workflow_slug: string;
  status: string;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  total_input_tokens: number;
  total_output_tokens: number;
  estimated_cost_usd: number;
  steps: ExecutionStep[];
}
```

**Step 2: Add `fetchExecutionDetail` to `api/executions.ts`**

```typescript
import { apiClient } from './client';
import type { ExecutionDetail } from '../types';

export async function fetchExecutionDetail(executionId: string): Promise<ExecutionDetail> {
  const resp = await apiClient.get<ExecutionDetail>(`/executions/${executionId}`);
  return resp.data;
}
```

**Step 3: Update `TestRunner.tsx` to show enriched detail after completion**

After the existing execution polling loop completes (status transitions to `completed` or `failed`),
call `fetchExecutionDetail` and render a summary panel:

Add a state field:
```tsx
const [detail, setDetail] = useState<ExecutionDetail | null>(null);
```

After `status` transitions to `completed`, fetch and set the detail:
```tsx
if (newStatus === 'completed' || newStatus === 'failed') {
  const d = await fetchExecutionDetail(executionId);
  setDetail(d);
}
```

Add a summary section below the step list:
```tsx
{detail && detail.status === 'completed' && (
  <div className="mt-4 border-t pt-3 space-y-2">
    <p className="text-xs font-semibold text-gray-500 uppercase">Execution Summary</p>
    <div className="grid grid-cols-3 gap-2 text-xs">
      <div className="bg-gray-50 rounded p-2">
        <p className="text-gray-400">Duration</p>
        <p className="font-mono font-medium">{detail.duration_ms ?? '—'}ms</p>
      </div>
      <div className="bg-gray-50 rounded p-2">
        <p className="text-gray-400">Tokens</p>
        <p className="font-mono font-medium">
          {detail.total_input_tokens} in / {detail.total_output_tokens} out
        </p>
      </div>
      <div className="bg-gray-50 rounded p-2">
        <p className="text-gray-400">Est. Cost</p>
        <p className="font-mono font-medium">${detail.estimated_cost_usd.toFixed(4)}</p>
      </div>
    </div>
    <div className="space-y-1">
      {detail.steps.map(step => (
        <div key={step.step_id} className="text-xs border rounded p-2 bg-white">
          <div className="flex items-center justify-between">
            <span className="font-medium">{step.step_name ?? step.step_id}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              step.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
            }`}>{step.status}</span>
          </div>
          {step.model && (
            <p className="text-gray-400 mt-0.5">
              {step.model}
              {step.input_tokens != null && ` · ${step.input_tokens}↑ ${step.output_tokens}↓ tokens`}
              {step.duration_ms != null && ` · ${step.duration_ms}ms`}
            </p>
          )}
        </div>
      ))}
    </div>
  </div>
)}
```

**Step 4: Manual smoke test**

1. Open `http://localhost:5173`, build a simple Agent → Output workflow
2. Click Test (toolbar) → enter `{"message": "hello"}` → Run
3. After completion, the summary panel appears below the step list
4. Duration, token counts, and estimated cost are displayed

**Step 5: Commit**

```bash
git add frontend/src/components/TestRunner.tsx \
        frontend/src/api/executions.ts \
        frontend/src/types/index.ts
git commit -m "feat: show execution detail (tokens, cost, duration) in TestRunner after completion"
```

---

## Execution Order and Parallelism

```
Can run in parallel NOW:
  - Track E2E  (Task E1 + E2)
  - Track FE-1 (Task FE1-1, FE1-2, FE1-3)
  - Track FE-2 (Task FE2-1, FE2-2, FE2-3, FE2-4)
  - Track FE-4 (Task FE4-1)  ← static content, no dependencies

Run after FE-2 lands (auth must work):
  - Track FE-3 (Task FE3-1)

Run after E1 (node_factory fix) lands:
  - Track OBS  (Task OBS-1, OBS-2, OBS-3)
```

## Final Verification

After all tracks are merged:

```bash
# Backend unit tests
cd backend && python -m pytest --tb=short -q

# E2E tests (Docker Compose must be running)
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin"
docker compose up -d
pytest tests/e2e/ -v -s

# Frontend build
cd frontend && npm run build
```

All must pass green.
