# FlowForge - Open-Source Hybrid Workflow Orchestrator

## Vision

FlowForge is a production-grade, multi-tenant workflow orchestration platform that lets
non-technical users build deterministic workflows mixing tool nodes (DB queries, ML models,
APIs, code) and agent nodes (LLM-powered) through a visual drag-and-drop builder.

The visual builder produces a structured YAML workflow definition that is compiled into an
executable LangGraph state machine at deploy time.

## Key Principles

1. LLM only when needed - most nodes are deterministic. Agent nodes used only for language tasks.
2. Non-technical authoring - constrained visual builder, 6 node types, dropdown-driven.
3. Production multi-tenant - stateless workers, DB-backed sessions, horizontal scaling.
4. Open source - MIT license throughout.

## Tech Stack

| Layer           | Technology                                    |
|-----------------|-----------------------------------------------|
| Frontend        | React 18, TypeScript, React Flow, Zustand     |
| Backend API     | Python 3.12, FastAPI, Pydantic v2              |
| Compiler        | Custom Python (YAML to LangGraph)              |
| Runtime         | LangGraph                                      |
| LLM             | LiteLLM                                        |
| Tool Protocol   | MCP Python SDK                                 |
| Templates       | Jinja2                                         |
| Database        | PostgreSQL 16, SQLAlchemy 2.0, Alembic         |
| Queue           | Redis 7 Streams                                |
| Vector DB       | Qdrant                                         |
| Containers      | Docker, docker-compose, Kubernetes             |

## Spec Documents (docs/)

- 01-ARCHITECTURE.md - System architecture and component design
- 02-YAML-SCHEMA.md - Workflow YAML format reference
- 03-COMPILER.md - YAML to LangGraph compiler
- 04-WORKER.md - Stateless worker pool
- 05-TOOL-PROTOCOL.md - MCP tool integration
- 06-AGENT-PROFILES.md - Agent profile format
- 07-VISUAL-BUILDER.md - React frontend spec
- 08-CONTROL-PLANE-API.md - REST API spec
- 09-DATA-MODEL.md - Database schema
- 10-MULTI-TENANCY.md - Tenant isolation and scaling
- 11-DEPLOYMENT.md - Docker and Kubernetes deployment
- 12-IMPLEMENTATION-PLAN.md - Phased build plan

## Repository Structure

```
flowforge/
  backend/              Python (FastAPI) - control plane + workers + compiler
  frontend/             React + TypeScript - visual builder
  mcp-tools/            Example MCP tool servers
  agent-profiles/       Agent definition .md files
  response-templates/   Jinja2 response templates
  examples/             Example workflow YAML files
  k8s/                  Kubernetes manifests
  docker-compose.yml    Local dev environment
```
