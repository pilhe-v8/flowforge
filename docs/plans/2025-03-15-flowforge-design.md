# FlowForge — Full Platform Design

**Date:** 2025-03-15  
**Scope:** Full platform implementation (all 7 phases from spec)  
**Approach:** Strict spec fidelity — skeleton-first, then implement layer by layer  
**Status:** Approved

---

## 1. Overview

FlowForge is a production-grade, multi-tenant workflow orchestration platform. Non-technical users design deterministic workflows mixing tool nodes (APIs, ML models, DB queries) and agent nodes (LLM-powered) through a visual drag-and-drop builder. The builder produces structured YAML, which is compiled into an executable LangGraph state machine at deploy time.

### Key Principles

1. LLM only when needed — most nodes are deterministic.
2. Non-technical authoring — constrained visual builder, 6 node types, dropdown-driven.
3. Production multi-tenancy — stateless workers, DB-backed sessions, horizontal scaling.
4. Open source — MIT license throughout.

---

## 2. Repository Structure

```
flowforge/
  backend/                   # Python 3.12 FastAPI monolith (API + compiler + worker)
    flowforge/
      main.py                # FastAPI app entry point
      config.py              # Pydantic-settings config
      compiler/
        parser.py            # WorkflowParser → WorkflowDef AST
        validator.py         # WorkflowValidator (reference + variable checks)
        graph_builder.py     # GraphBuilder → LangGraph CompiledStateGraph
        node_factory.py      # NodeFactory (builds 6 node type callables)
        safe_eval.py         # SafeExprEvaluator (AST-based, no eval())
        schema.json          # JSON Schema for YAML validation
      worker/
        __main__.py          # Worker process entry point
        consumer.py          # StreamConsumer (Redis Streams XREADGROUP)
        lock.py              # SessionLock (SET NX EX + Lua release)
        executor.py          # Executor (LangGraph ainvoke)
        session_manager.py   # SessionManager (PostgreSQL CRUD)
        graph_cache.py       # GraphCache (Redis pickle, 5min TTL)
      api/
        workflows.py         # /workflows: CRUD, deploy, rollback, versions
        tools.py             # /tools: catalogue, register, refresh
        agents.py            # /agents: CRUD
        executions.py        # /executions: trigger, get, list + WebSocket
        tenants.py           # /tenants: admin CRUD
        templates.py         # /templates: CRUD
        webhooks.py          # /webhooks/{slug}: incoming triggers
      models/                # SQLAlchemy ORM (10 tables)
      db/
        session.py           # Async DB session factory (asyncpg)
        migrations/          # Alembic migration versions
      tools/
        mcp_client.py        # MCPToolClient (mcp Python SDK)
        http_client.py       # HTTPToolClient (httpx)
        executor.py          # ToolExecutor (routes by URI scheme)
        discovery.py         # MCPDiscovery (list_tools + catalogue)
      llm/
        client.py            # LLMClient (LiteLLM, retry, circuit breaker)
      agents/
        loader.py            # ProfileLoader (Markdown parser)
        prompt_builder.py    # PromptBuilder (system + user messages)
      templates/
        engine.py            # Jinja2 template engine
    pyproject.toml
    Dockerfile
    alembic.ini
  frontend/                  # React 18 + TypeScript + Vite
    src/
      components/
        Nodes/               # ToolNode, AgentNode, RouterNode, GateNode, TriggerNode, OutputNode
        Panels/              # ToolPanel, AgentPanel, RouterPanel, GatePanel, TriggerPanel, OutputPanel
        shared/              # VariableSelector, ConditionBuilder
        Layout/              # Toolbar, NodePalette, ValidationBar
      stores/
        workflowStore.ts     # Zustand: nodes, edges, undo/redo, save/deploy
        toolCatalogueStore.ts # Zustand: tools, agents, fetch
      utils/
        variableResolver.ts  # BFS upstream variable tracking
        yamlSerializer.ts    # Canvas ↔ YAML bidirectional conversion (dagre)
        validation.ts        # Real-time workflow validation
      hooks/
        useAvailableVariables.ts
      types/                 # TypeScript interfaces for all entities
      api/                   # Typed API client functions
    package.json
    Dockerfile
    vite.config.ts
    tailwind.config.ts
  mcp-tools/                 # Example MCP servers
    customer-lookup/server.py
    sentiment-analysis/server.py
    email-sender/server.py
  agent-profiles/            # Markdown agent profiles
    classifier.md
    tech-support.md
    reply-drafter.md
  response-templates/        # Jinja2 .j2 templates
    password_reset.j2
    order_status.j2
    billing_response.j2
  examples/
    customer-service.yaml
  k8s/                       # Kubernetes manifests
    namespace.yaml
    backend-deployment.yaml
    worker-deployment.yaml
    frontend-deployment.yaml
    redis.yaml
    postgres.yaml
    qdrant.yaml
    hpa.yaml
    ingress.yaml
    configmap.yaml
    secrets.yaml
  docker-compose.yml
```

---

## 3. Data Model

All tables in PostgreSQL 16 via SQLAlchemy 2.0 async (asyncpg driver). Every table except `tenants` includes a `tenant_id` FK for row-level isolation.

| Table               | Purpose                                                   |
|---------------------|-----------------------------------------------------------|
| `tenants`           | Organisations; config JSONB (LLM keys encrypted, budgets) |
| `users`             | Per-tenant users; roles: viewer / editor / admin           |
| `workflows`         | Workflow metadata; slug+tenant unique                      |
| `workflow_versions` | YAML definition + status (draft/active/archived)           |
| `sessions`          | Per-user conversation state (JSONB), expires 24h           |
| `executions`        | Audit record per trigger (queued/running/completed/failed) |
| `execution_steps`   | One row per node executed (input/output JSONB)             |
| `tool_registrations`| Per-tenant MCP endpoints + discovered tool schemas         |
| `agent_profiles`    | Slug + markdown content + parsed fields                    |
| `response_templates`| Jinja2 template content + variable list                   |
| `token_usage`       | Per-LLM-call tracking (model, tokens, cost_usd)           |

Alembic manages migrations; initial schema in `001_initial_schema.py`.

---

## 4. Compiler Pipeline

Seven stages, running at deploy time (and on cache miss in workers):

1. **Parse** — `yaml.safe_load` → `WorkflowParser.parse()` → `WorkflowDef` + `StepDef` dataclasses
2. **Schema Validate** — `jsonschema` check against `schema.json`
3. **Build AST** — done in step 1 (combined)
4. **Validate References** — `WorkflowValidator`: tool URIs exist in catalogue, agent slugs exist, `next`/route/gate targets are valid step IDs
5. **Validate Variables** — BFS backwards through graph; every `{{step_id.var}}` must be produced upstream
6. **Build Graph** — `GraphBuilder`: `StateGraph(dict)`, adds nodes via `NodeFactory`, wires edges (conditional for router/gate)
7. **Compile** — `graph.compile()` → `CompiledStateGraph`

**Safe Expression Evaluator** for gate rules and fallback conditions: AST parsing with operator whitelist (`==`, `!=`, `<`, `>`, `<=`, `>=`, `and`, `or`, `not`, `in`, `len()`, `contains()`, `starts_with()`, `is_empty()`). No `eval()` used.

---

## 5. Worker Pool

- Separate process (`python -m flowforge.worker`); shares codebase with API
- Joins consumer group `flowforge-workers` on stream `flowforge:messages:{tenant_id}`
- `XREADGROUP` blocks 5s per poll; processes 1 message per iteration
- Session lock: Redis `SET NX EX 120`; released via Lua script (ownership check)
- Graph cache: Redis pickle, 5min TTL; cache miss recompiles from DB
- DLQ after 3 retries: messages moved to `flowforge:messages:dlq`
- Health endpoint on port 8081 (configurable) for K8s liveness probe
- Scales via HPA on Redis Stream lag metric (min 2, max 50 replicas)

---

## 6. Tool Integration

- **MCP** (primary): `MCPToolClient` pools `ClientSession` per endpoint; calls `call_tool()`
- **HTTP** (fallback): `httpx.AsyncClient`; bearer token and API key auth
- **ToolExecutor** routes by URI scheme: `mcp://` → MCP, `http(s)://` → HTTP
- **MCPDiscovery** calls `list_tools()` at registration and every 5 minutes
- Tool catalogue served to frontend for dropdown population

---

## 7. Agent Integration

- **ProfileLoader**: parses Markdown sections (Role, Context, Guidelines, Output, Examples)
- **PromptBuilder**: builds `[{role: system, ...}, {role: user, ...}]` message list
- **LLMClient**: LiteLLM wrapper; temperature 0.3; retry 3x with exponential backoff; circuit breaker; token usage tracked to `token_usage` table

---

## 8. API (FastAPI, `/api/v1`)

| Route prefix         | Endpoints                                                     |
|----------------------|---------------------------------------------------------------|
| `/workflows`         | List, get, create, update, deploy, rollback, list versions    |
| `/tools`             | Catalogue, register, refresh                                  |
| `/agents`            | List, get, create/update                                      |
| `/executions`        | Trigger, get, list + WebSocket live trace                     |
| `/tenants`           | Create, get (admin only)                                      |
| `/templates`         | List, get, create/update                                      |
| `/webhooks/{slug}`   | Incoming webhook trigger                                      |

Auth: JWT bearer token (`sub`, `tenant_id`, `role`, `exp`). CORS enabled for all origins in dev.

---

## 9. Frontend (React 18 + TypeScript)

- **Canvas**: React Flow v12; 6 drag-and-drop node types from left palette
- **Properties Panel**: right-side context-sensitive configuration per node type
- **Variable Tracking**: `variableResolver.ts` — BFS upstream, recalculates on every graph change; drives all dropdown options
- **YAML Serializer**: bidirectional canvas ↔ YAML; dagre auto-layout on import
- **Validation**: real-time, runs on every change; red borders on invalid nodes; bottom bar with error count
- **State Management**: Zustand with undo/redo history (workflow store + tool catalogue store)
- **Test Runner**: POST trigger → WebSocket → step highlights on canvas, output side panel

---

## 10. Multi-Tenancy & Deployment

- DB queries auto-filtered by `tenant_id` (SQLAlchemy middleware)
- Redis keys namespaced: `flowforge:{tenant_id}:*`
- Qdrant: one collection per tenant (`flowforge_{slug}_memory`)
- Per-tenant: tool registrations, agent profiles, LLM API keys (encrypted), token budgets

**Docker Compose** (local dev): postgres:16, redis:7, qdrant, backend (port 8000), worker, frontend (port 5173)

**Kubernetes**: Namespace, deployments for backend/worker/frontend, StatefulSets for postgres/redis/qdrant, HPA for workers, Ingress with nginx

---

## 11. Implementation Order (Skeleton-First)

### Step 1: Full project skeleton
All directories, config files, Dockerfiles, docker-compose, K8s manifests, `pyproject.toml`, `package.json`. No logic yet.

### Step 2: Database + migrations
All 10 SQLAlchemy models, Alembic migration `001_initial_schema.py`.

### Step 3: Compiler
`parser.py`, `validator.py`, `safe_eval.py`, `graph_builder.py`, `node_factory.py`, `schema.json`. Full pipeline with tests.

### Step 4: Worker
`consumer.py`, `lock.py`, `executor.py`, `session_manager.py`, `graph_cache.py`. Connects to Redis + PG.

### Step 5: Tool + Agent Integration
`mcp_client.py`, `http_client.py`, `tool_executor.py`, `discovery.py`, `llm/client.py`, `agents/loader.py`, `agents/prompt_builder.py`, `templates/engine.py`.

### Step 6: API
All FastAPI routers, JWT middleware, tenant filter middleware.

### Step 7: Example MCP servers + Agent profiles + Templates
`mcp-tools/`, `agent-profiles/`, `response-templates/`.

### Step 8: Frontend
Full React app: nodes, panels, stores, utils, hooks, API client.

### Step 9: Kubernetes manifests + Hardening
K8s YAML, HPA, health checks, Prometheus metrics, structured logging.
