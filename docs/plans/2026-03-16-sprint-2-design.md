# FlowForge Sprint 2 — Design Document

**Date:** 2026-03-16  
**Status:** Approved

---

## Overview

Six independent work tracks, each scoped and self-contained. They can be parallelised across agents or sessions.

| Track | Area | Priority |
|---|---|---|
| E2E | End-to-end automated test + LLM agent-node bug fix | High |
| FE-1 | Node deletion (keyboard + button) | High |
| FE-2 | Frontend error visibility + auth dev bypass | High |
| FE-3 | Catalogue panel (agents & tools browser) | Medium |
| FE-4 | Node-type definitions panel | Medium |
| OBS | Observability: token tracking + execution detail UI | Medium |

---

## Track E2E — End-to-End Automated Test

### Goal
Prove the full request path works: API → DB → Redis Stream → Worker → LangGraph → LiteLLM Proxy → real Mistral LLM → execution recorded in DB.

### Bug to fix first (blocker)
`backend/flowforge/compiler/node_factory.py` `_build_agent_node` only calls the LLM when **both** `self.profiles` and `self.llm` are set. `graph_cache.py` passes `profile_loader=None`, so the agent node silently returns empty strings and the LLM is never called.

**Fix:** Add a no-profile fallback path: when `profile_loader is None`, build a minimal `[{"role":"system","content":"You are a helpful assistant."}, {"role":"user","content": str(context)}]` message list and call `self.llm.chat(messages)` directly. The agent node must produce a non-empty `response_content` regardless of whether a profile loader is wired.

### Test structure
- Location: `tests/e2e/` (new directory, not inside `backend/tests/`)
- Files: `conftest.py` + `test_e2e_workflow.py` + `e2e_workflow.yaml`
- Runner: `pytest tests/e2e/ -v` against the live Docker Compose stack at `localhost:8000`

### Minimal workflow YAML
A 2-step workflow: `agent` node → `output` node. The output node fires a no-op HTTP action (to `http://localhost:1/noop`) which will fail gracefully — the test only asserts on the agent step's output.

```yaml
workflow:
  name: E2E Hello World
  slug: e2e-hello-world
  version: 1
  description: Minimal E2E test workflow
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

### Test steps
1. Mint an admin JWT using `jwt.encode` + `FLOWFORGE_JWT_SECRET=dev-secret-change-in-production`
2. `POST /api/v1/tenants` → get `tenant_id`; embed in all subsequent JWTs
3. `POST /api/v1/workflows` with the YAML above
4. `POST /api/v1/workflows/e2e-hello-world/deploy`
5. `POST /api/v1/executions/trigger` with `{"workflow_slug": "e2e-hello-world", "input_data": {"message": "Hello"}}`
6. Poll `GET /api/v1/executions/{id}` every 2 s for up to 60 s until `status == "completed"`
7. Assert `execution["status"] == "completed"` and that the `greet` step's `output["reply"]` is a non-empty string

### Success criteria
- Test passes green in a single `pytest` run
- Worker logs show the LiteLLM HTTP call being made
- Execution record in DB has `status=completed` and a non-empty agent output

---

## Track FE-1 — Node Deletion

### Current state
`removeNode(id)` exists in `workflowStore.ts` and is correctly implemented (cascades edges, pushes undo history, clears selection, marks dirty). But it is **never triggered from any UI element**.

### Design
Three complementary delete triggers, all routing through the same `removeNode` store action:

**1. Keyboard Delete key (via React Flow)**
In `App.tsx`, add `onNodesDelete` and `onEdgesChange` (for edge removal) wired to the store actions, and set `deleteKeyCode="Delete"` on `<ReactFlow>`. This enables the native React Flow keyboard handler while routing deletions through the store for undo tracking.

```tsx
const onNodesDelete = useCallback(
  (deleted: Node[]) => { deleted.forEach(n => removeNode(n.id)); },
  [removeNode],
);
```

**2. Delete button on selected nodes**
Each node component (`TriggerNode`, `ToolNode`, `AgentNode`, `RouterNode`, `GateNode`, `OutputNode`) already receives `selected` as a prop. When `selected === true`, render a small `×` button in the top-right corner of the node card. Clicking it calls `removeNode(id)`. This is the most discoverable approach for mouse users.

**3. Delete button in the Properties Panel**
A "Delete node" button at the bottom of the right-side panel, visible only when a node is selected. This is the accessibility fallback.

### Files changed
- `frontend/src/App.tsx` — add `onNodesDelete`, `deleteKeyCode`
- `frontend/src/components/Nodes/TriggerNode.tsx` (and all 5 other node files) — add `×` button
- `frontend/src/components/Panels/` — add delete button at panel footer

---

## Track FE-2 — Frontend Error Visibility + Auth Dev Bypass

### Current state (three compounding failures)
1. No login page / no token ever set → every API call returns 401 silently
2. No Axios response interceptor → 4xx/5xx thrown promises go uncaught
3. No toast library, no ErrorBoundary → even caught errors have nowhere to display

### Design

**Step 1 — Dev auth bypass**
Add a `DEV_JWT` constant generated at build time (Vite `import.meta.env`) or hard-coded for local dev. On app startup, if `localStorage.getItem('flowforge_token')` is null, auto-set it to a pre-minted dev JWT (`sub: "dev-user"`, `tenant_id: <known-dev-tenant>`, `role: "admin"`, signed with the dev secret). This eliminates the 401 cascade without requiring a full auth UI. The dev token is generated by a small script checked into `scripts/mint_dev_token.py`.

**Step 2 — Axios response interceptor**
Add a response interceptor in `api/client.ts` that:
- On 401 → clears the token from `localStorage`, shows a toast "Session expired — please reload"
- On 4xx (client errors) → shows a toast with the API error message (`detail` field from FastAPI)
- On 5xx → shows a toast "Server error — check logs"

**Step 3 — Toast library**
Install `sonner` (lightweight, Radix-based, zero-config). Wrap `<App>` with `<Toaster>` in `main.tsx`. Expose a `toast.error(msg)` helper used by the interceptor and all store actions that currently use `console.error`.

**Step 4 — ErrorBoundary**
Add a simple `ErrorBoundary` React class component in `src/components/shared/ErrorBoundary.tsx`. Wrap `<App>` with it in `main.tsx`. On error, render a centered message rather than a blank screen.

**Step 5 — Surface stored errors**
- Read `useToolCatalogueStore(s => s.error)` in `App.tsx` and `toast.error()` when non-null
- Add try/catch to `workflowStore.save()` and `workflowStore.deploy()` and call `toast.error()`

### Files changed
- `frontend/package.json` — add `sonner`
- `frontend/src/main.tsx` — add `<Toaster>` + `<ErrorBoundary>`
- `frontend/src/api/client.ts` — add response interceptor
- `frontend/src/stores/workflowStore.ts` — add try/catch to `save()`, `deploy()`
- `frontend/src/App.tsx` — dev token bootstrap, surface catalogue error
- `scripts/mint_dev_token.py` — new helper script
- `frontend/src/components/shared/ErrorBoundary.tsx` — new component

---

## Track FE-3 — Catalogue Panel

### Goal
A browsable left-side panel showing all registered tools and agent profiles, so the user can see what is available before placing nodes. Clicking a catalogue item adds a pre-configured node to the canvas.

### Design
**Location:** Replace the current `NodePalette` (which shows generic node-type buttons) with a two-tab panel:
- **Tab 1: Node Types** — the existing 6 generic node-type buttons (keep current behaviour)
- **Tab 2: Catalogue** — scrollable list of tools and agents from the backend, with name, description, and a "+ Add" button per item

The catalogue tab consumes `toolCatalogueStore` (already fetches data). Clicking "+ Add" on a tool entry calls `addNode('tool', {x:250, y:100})` then immediately calls `updateNodeData(newId, { toolUri: tool.uri, toolName: tool.name })` so the new node is pre-configured.

**UI structure:**
```
┌─────────────────────┐
│ [Node Types] [Catalogue] │ ← tabs
├─────────────────────┤
│ 🔍 Search...         │ ← filter input
├─────────────────────┤
│ TOOLS               │
│  🔧 Customer Lookup │ + │
│     mcp://crm-service...│
│  🔧 Sentiment Analysis│+│
│     mcp://ml-services...│
├─────────────────────┤
│ AGENTS              │
│  🧠 Intent Classifier│+│
│  🧠 Reply Drafter   │ + │
│  🧠 Tech Support    │ + │
└─────────────────────┘
```

### Files changed
- `frontend/src/components/Layout/NodePalette.tsx` — refactor to tabbed panel
- `frontend/src/stores/toolCatalogueStore.ts` — ensure `description` from tools is stored

---

## Track FE-4 — Node-Type Definitions Panel

### Goal
A right-side expandable reference panel (collapsible drawer or help sidebar) that shows the definition and field descriptions for the currently selected node type. Helps users understand what each field means without leaving the app.

### Design
**Location:** A collapsible `?` help drawer attached to the right side of the Properties Panel. When expanded, it shows:
- **Node type name + icon**
- **One-sentence description** of what this node type does
- **Field reference table**: field name → description → example value

Definitions are statically embedded in a `NODE_DEFINITIONS` constant (no API call needed — these are framework-level concepts, not user data).

Example for `agent` node type:
```
🧠 Agent Node
Runs an LLM-powered agent from your agent profile library.

Field         | Description                          | Example
agent         | Slug of the agent profile to use     | "reply-drafter"
model         | Override the agent's default model   | "gpt-4o-mini"
context.*     | Variables passed as context to LLM   | message: "{{trigger.body}}"
output        | Variable names the agent will return  | ["reply"]
next          | ID of the next step to execute       | "quality_gate"
```

### Files changed
- `frontend/src/components/shared/NodeDefinitions.ts` — static definitions object
- `frontend/src/components/Panels/DefinitionDrawer.tsx` — new collapsible component
- `frontend/src/components/Layout/PropertiesPanel.tsx` — embed `<DefinitionDrawer>` below the active panel

---

## Track OBS — Observability: Token Tracking + Execution Detail UI

### Current state
- `TokenUsage` DB table exists but is always empty (tokens discarded in `node_factory.py`)
- `execution.duration_ms` always null (never written by `AuditLog`)
- `GET /executions/{id}` response missing: model, tokens, timestamps, cost
- Frontend has no execution history page; `TestRunner` shows status only

### Design

#### Backend fixes (3 files)

**1. `node_factory.py` — capture tokens in audit trail**
After `response = await self.llm.chat(messages, model=model)`, add to the `_audit_trail` entry:
```python
{
  "step_id": step.id, "step_name": step.name, "step_type": "agent",
  "model": model,
  "input_tokens": response.input_tokens,
  "output_tokens": response.output_tokens,
  "started_at": started_at.isoformat(),
  "completed_at": completed_at.isoformat(),
  "duration_ms": int((completed_at - started_at).total_seconds() * 1000),
  ...
}
```
Also wrap each node callable with timing (`started_at = datetime.utcnow()` before, `completed_at = datetime.utcnow()` after).

**2. `consumer.py` AuditLog — write TokenUsage rows + execution timing**
- Compute `started_at` / `duration_ms` on the Execution row from audit trail entries
- Insert one `TokenUsage` row per agent step that has `input_tokens` / `output_tokens` in the trail

**3. `api/executions.py` GET /{id} — enrich response**
Add to the response:
- `queued_at`, `started_at`, `completed_at`, `duration_ms` at execution level
- `input_data`, `output_data` at execution level
- `workflow_slug` at execution level
- Per step: `step_name`, `model`, `input_tokens`, `output_tokens`, `duration_ms`
- Execution-level summary: `total_input_tokens`, `total_output_tokens`, `estimated_cost_usd`
- Order steps by `started_at`

#### Frontend additions (2 components)

**1. Extend `TestRunner.tsx`**
After execution completes, fetch `GET /executions/{id}` and render an enriched summary:
- Per-step card: step name, type, model used, duration, input/output tokens, output preview
- Footer: total tokens, estimated cost, total duration

**2. Execution history panel (stretch)**
A new `ExecutionsPanel` accessible via a history icon in the `Toolbar`. Lists recent executions (from `GET /executions`) and allows clicking one to open the enriched detail view.

### Cost estimation
Hardcode a `COST_PER_1K_TOKENS` table for known models:
```python
COST_TABLE = {
  "mistral-large-latest": {"input": 0.003, "output": 0.009},
  "gpt-4o": {"input": 0.005, "output": 0.015},
  "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}
```
Cost is computed at query time (not stored) to avoid staleness.

---

## Dependency Map

```
E2E   ← fixes node_factory.py LLM bug (prerequisite for OBS token capture too)
FE-2  ← prerequisite for FE-3, FE-4 (app must work before adding panels)
FE-1  ← independent
FE-3  ← depends on FE-2 (auth must work to fetch catalogue)
FE-4  ← independent (static content, no API)
OBS   ← depends on E2E node_factory.py fix
```

**Safe parallel execution:** E2E + FE-1 + FE-2 + FE-4 can all run in parallel.  
FE-3 and OBS should start after their prerequisites land.
