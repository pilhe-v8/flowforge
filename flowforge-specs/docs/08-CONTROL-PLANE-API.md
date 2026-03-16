# 08 - Control Plane API Specification

## Overview

The control plane is a FastAPI application serving the visual builder, managing
workflows, and enqueuing messages for workers.

## Base Configuration

- Base URL: /api/v1
- Content-Type: application/json
- Auth: JWT bearer token containing sub, tenant_id, role, exp

## Endpoints

### Workflows

#### List Workflows
```
GET /workflows?page=1&per_page=20&search=customer

Response 200:
{
  "workflows": [{
    "slug": "customer-service",
    "name": "Customer Service",
    "version": 3,
    "status": "active",
    "trigger_type": "email_received",
    "node_count": 12,
    "execution_count_24h": 847,
    "created_at": "2026-01-15T10:00:00Z",
    "updated_at": "2026-03-10T14:30:00Z"
  }],
  "total": 5, "page": 1, "per_page": 20
}
```

#### Get Workflow
```
GET /workflows/{slug}?version=3

Response 200:
{
  "slug": "customer-service",
  "name": "Customer Service",
  "version": 3,
  "status": "active",
  "yaml_definition": "workflow:\n  name: ...",
  "compiled_at": "2026-03-10T14:30:00Z",
  "compilation_errors": []
}
```

#### Create Workflow
```
POST /workflows
Body: {"name": "Customer Service", "yaml_definition": "workflow:\n  ..."}
Response 201: {"slug": "customer-service", "version": 1, "status": "draft"}
```

#### Update Workflow (new version)
```
PUT /workflows/{slug}
Body: {"yaml_definition": "workflow:\n  ..."}
Response 200: {"slug": "...", "version": 4, "status": "draft", "compilation_errors": []}
```

#### Deploy Workflow
```
POST /workflows/{slug}/deploy
Body: {"version": 4}
Response 200: {"slug": "...", "version": 4, "status": "active", "deployed_at": "..."}
Response 422: {"errors": [{"step_id": "classify", "field": "tool", "message": "..."}]}
```

#### Rollback
```
POST /workflows/{slug}/rollback
Body: {"version": 3}
Response 200: {"slug": "...", "version": 3, "status": "active"}
```

#### List Versions
```
GET /workflows/{slug}/versions
Response 200: {"versions": [{"version": 4, "status": "draft", "created_at": "..."}, ...]}
```

### Tools

#### Get Catalogue
```
GET /tools/catalogue
Response 200: {"tools": [{"slug": "...", "name": "...", "uri": "...", "input_schema": {...}, "output_schema": {...}}]}
```

#### Register MCP Endpoint
```
POST /tools/register
Body: {"endpoint": "mcp://crm-service:9000", "name": "CRM Service"}
Response 201: {"endpoint": "...", "discovered_tools": [...], "registered_count": 3}
```

#### Refresh Discovery
```
POST /tools/refresh
Response 200: {"refreshed_endpoints": 3, "total_tools": 12, "new_tools": 1}
```

### Agent Profiles

#### List
```
GET /agents
Response 200: {"agents": [{"slug": "tech-support", "name": "...", "updated_at": "..."}]}
```

#### Get
```
GET /agents/{slug}
Response 200: {"slug": "...", "name": "...", "content": "# Tech Support Agent\n\n## Role\n...", "default_model": null}
```

#### Create/Update
```
PUT /agents/{slug}
Body: {"name": "...", "content": "# ...", "default_model": "gpt-4o"}
Response 200: {"slug": "...", "updated_at": "..."}
```

### Executions

#### Trigger Workflow
```
POST /executions/trigger
Body: {
  "workflow_slug": "customer-service",
  "input_data": {"sender": "jane@acme.com", "subject": "Help", "body": "..."},
  "session_id": "optional-existing-session-id"
}
Response 202: {"execution_id": "uuid", "session_id": "uuid", "status": "queued"}
```

#### Get Execution
```
GET /executions/{execution_id}
Response 200: {
  "execution_id": "uuid",
  "status": "completed",
  "duration_ms": 3420,
  "steps": [
    {"step_id": "lookup_customer", "type": "tool", "status": "completed", "duration_ms": 45, "input": {...}, "output": {...}},
    ...
  ]
}
```

#### List Executions
```
GET /executions?workflow_slug=customer-service&status=failed&page=1
Response 200: {"executions": [...], "total": 152, "page": 1}
```

### Tenants (admin only)

```
POST /tenants
Body: {
  "name": "Acme Corp", "slug": "acme-corp",
  "config": {"default_llm_model": "gpt-4o-mini", "daily_token_budget": 1000000, "max_concurrent_sessions": 100}
}
```

### Webhooks (incoming triggers)

```
POST /webhooks/{workflow_slug}
Headers: Authorization: Bearer {webhook_token}
Body: (arbitrary JSON)
Response 202: {"execution_id": "uuid", "status": "queued"}
```

### WebSocket: Live Execution Trace

```
WS /ws/executions/{execution_id}

Server pushes:
{"event": "step_started", "step_id": "classify", "timestamp": "..."}
{"event": "step_completed", "step_id": "classify", "duration_ms": 12, "output": {...}}
{"event": "workflow_completed", "duration_ms": 3420}
```

## Response Templates

```
GET /templates
PUT /templates/{slug}
Body: {"name": "Password Reset", "content": "Dear {{name}},\n\nClick here: {{reset_link}}...", "variables": ["name", "reset_link"]}
```

## FastAPI App Structure

```python
# backend/flowforge/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from flowforge.api import workflows, tools, agents, executions, tenants

app = FastAPI(title="FlowForge", version="0.1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(workflows.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(executions.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
```
