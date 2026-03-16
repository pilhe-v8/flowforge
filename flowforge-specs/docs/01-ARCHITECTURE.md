# 01 - Architecture Specification

## System Context

FlowForge is a multi-tenant platform where:
- Workflow Authors (non-technical) design workflows via a visual builder
- End Users trigger workflows (email, API, schedule)
- Developers create MCP tool servers and agent profiles
- Operators deploy and monitor the platform

## Component Responsibilities

### 1. Visual Builder (Frontend)
- Technology: React 18, TypeScript, React Flow, Zustand, Vite
- Constrained drag-and-drop canvas with exactly 6 node types
- Populates tool/agent dropdowns from backend API (MCP discovery)
- Tracks available variables through the graph for downstream dropdowns
- Real-time visual validation (red borders on broken connections)
- Serializes canvas state to YAML / deserializes YAML back to canvas
- Does NOT execute workflows, call LLMs, or call tools directly

### 2. Control Plane (Backend API)
- Technology: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic
- CRUD for workflows, tenants, agent profiles, response templates
- Validates YAML workflow definitions (schema + reference checks)
- Compiles YAML to LangGraph via the compiler module
- MCP tool discovery: queries registered MCP servers, builds tool catalogue
- Enqueues incoming messages to Redis Streams
- Manages workflow versions (each save = new version, rollback supported)
- Authentication and authorization (JWT, per-tenant)

### 3. Compiler (inside backend)
- Module: flowforge.compiler
- Pipeline: Parse YAML -> Validate schema -> Build AST -> Validate references -> Validate variables -> Build LangGraph -> Return compiled graph

### 4. Worker Pool (separate process, same codebase)
- Technology: Python, Redis Streams consumer, LangGraph executor
- Consumes messages from Redis Streams (one consumer group, multiple consumers)
- Acquires per-session distributed lock (Redis SET NX EX 120)
- Loads session state from PostgreSQL
- Loads compiled graph from cache or recompiles
- Executes graph with session state
- Saves updated state, writes audit log, ACKs message, releases lock
- Stateless: any worker can process any tenant's message

### 5. Tool Integration (MCP)
- Technology: MCP Python SDK, httpx for HTTP fallback
- Connects to registered MCP servers, calls list_tools() for discovery
- Builds ToolCatalogue: name, description, URI, input/output JSON schemas
- At runtime calls tools via call_tool() with resolved parameters
- Supports HTTP and gRPC endpoints as fallback for non-MCP tools

### 6. LLM Layer
- Technology: LiteLLM
- Routes LLM calls to configured providers per tenant
- Retry with exponential backoff + circuit breaker
- Token usage tracking per tenant
- Response caching for deterministic calls (e.g. classification)

### 7. Data Stores
| Store      | Purpose                                                  |
|------------|----------------------------------------------------------|
| PostgreSQL | Workflows, sessions, tenants, audit logs, profiles       |
| Redis      | Message queue (Streams), locks, rate limits, graph cache  |
| Qdrant     | Vector memory for RAG, per-tenant collections             |

## Request Lifecycle

```
1.  Trigger fires (email webhook, API call, schedule)
2.  Control Plane authenticates, extracts tenant_id + user_id
3.  Creates message envelope:
    {message_id, tenant_id, user_id, session_id, workflow_slug, input_data, timestamp}
4.  Enqueues to Redis Stream: flowforge:messages:{tenant_id}
5.  Worker picks up message via XREADGROUP
6.  Worker acquires lock: SET session:{session_id} NX EX 120
7.  Worker loads session from PostgreSQL (or creates new)
8.  Worker loads compiled graph from cache (or recompiles from stored YAML)
9.  Worker executes graph node by node:
    a. Resolve input variables from state using {{step_id.var}}
    b. Execute node function:
       - tool node     -> MCP client call / HTTP call
       - agent node    -> LiteLLM call with agent profile prompt
       - router node   -> evaluate routing expression, return edge name
       - gate node     -> evaluate rules, return edge name
       - deterministic -> run Python function (parse, format, template)
       - output node   -> call output tool (send email, create ticket)
    c. Write outputs to session state
    d. Log step execution to audit trail
    e. Follow edges based on return values
10. Worker saves session state to PostgreSQL
11. Worker ACKs message in Redis Stream, releases lock
```

## Concurrency Model
- Per-session ordering via distributed lock (one message per session at a time)
- Cross-session parallelism across workers
- N workers share one Redis consumer group (exactly-once delivery per message)
- Lock timeout 120s; crashed worker lock auto-expires

## Error Handling
| Failure              | Recovery                                               |
|----------------------|--------------------------------------------------------|
| Worker crash         | Lock expires, message remains pending, another claims  |
| LLM timeout          | Retry 3x with backoff, then route to escalation        |
| MCP tool unreachable | Retry once, then mark errored, admin notified          |
| Invalid YAML         | Rejected at compile time, never reaches workers        |
| Database unreachable | Worker retries with backoff, does not ACK message      |

## Security
- All DB queries include tenant_id filter
- Qdrant uses per-tenant collections
- Redis keys namespaced by tenant
- MCP registrations scoped per-tenant
- LLM API keys stored encrypted per-tenant
