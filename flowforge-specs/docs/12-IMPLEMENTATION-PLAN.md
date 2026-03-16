# 12 - Implementation Plan

## Phase 1: Foundation (Week 1-2)
Goal: Backend skeleton + compiler + single workflow via API.
- Project scaffolding: pyproject.toml, FastAPI, config
- Database: SQLAlchemy async, Alembic migrations (all tables)
- Compiler v1: parser, validator, graph_builder, node_factory (deterministic+output only)
- Safe expression evaluator
- Worker v1: consumer, lock, session_manager, executor, graph cache
- API v1: CRUD workflows, trigger, get execution
- Docker Compose
- Test: deterministic workflow end-to-end

## Phase 2: Tool Integration (Week 3-4)
Goal: MCP tool nodes work with example servers.
- MCP client, HTTP client, discovery, registry
- Tool API: catalogue, register, refresh
- Node factory: tool nodes + fallback
- Example MCP servers: customer-lookup, sentiment, email-sender
- Validator: tool URI + schema checks
- Test: tool workflow end-to-end

## Phase 3: Agent Integration (Week 5-6)
Goal: Agent nodes with LLM via LiteLLM.
- Profile loader, prompt builder, agent CRUD API
- LLM client: LiteLLM wrapper, retry, circuit breaker, token tracking
- Node factory: agent nodes
- Template engine: Jinja2 + CRUD API
- Example profiles + templates
- Test: full customer-service workflow

## Phase 4: Visual Builder (Week 7-10)
Goal: React frontend for visual design.
- Vite + React 18 + TS + Tailwind + React Flow v12 + Zustand
- Canvas, palette, connection validator
- 6 node components, 6 panels
- VariableSelector, ConditionBuilder
- Variable tracking (variableResolver.ts)
- YAML serializer/deserializer (dagre layout)
- Toolbar: Save, Deploy, Versions, Undo/Redo
- Validation (real-time, visual)
- Test runner (WebSocket live trace)
- Test: build workflow from UI, deploy, run

## Phase 5: Multi-Tenancy (Week 11-12)
- JWT auth, user/tenant management
- DB tenant filter middleware
- Redis namespacing, Qdrant per-tenant collections
- Rate limiting, token budgets
- Per-tenant LLM config + encrypted keys

## Phase 6: Hardening (Week 13-14)
- DLQ, retry, circuit breaker
- Structured logging, Prometheus metrics
- Unit/integration/E2E/component tests
- Docs: OpenAPI, user guide, dev guide
- K8s manifests, HPA, health checks

## Phase 7: Advanced (Week 15+)
- Webhook/schedule triggers
- Execution dashboard, token analytics
- Human-in-the-loop, parallel branches
- A/B prompt testing, workflow import/export
- RAG via Qdrant

## Dependencies
Phase 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7
(Phase 4 depends on 2+3 for API dropdowns)

## Team: 2 developers, ~14 weeks to production
