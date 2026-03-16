# 10 - Multi-Tenancy and Scaling Specification

## Overview

FlowForge is designed for multi-tenant operation where each tenant (organisation)
has isolated data, tools, agents, and workflows, while sharing the same infrastructure.

## Tenant Isolation

### Database Isolation
- Every table includes a tenant_id column
- All queries MUST include WHERE tenant_id = :tenant_id
- SQLAlchemy query middleware auto-injects tenant filter

### Redis Isolation
- All Redis keys prefixed: flowforge:{tenant_id}:*
- Stream keys: flowforge:messages:{tenant_id}
- Lock keys: flowforge:lock:{tenant_id}:{session_id}
- Cache keys: flowforge:graph:{tenant_id}:{workflow_slug}

### Qdrant Isolation
- One collection per tenant: flowforge_{tenant_slug}_memory
- Created on tenant provisioning, deleted on tenant removal

### MCP Tool Isolation
- Tool registrations are per-tenant
- Catalogue API returns only requesting tenant's tools
- Workers resolve tool URIs against tenant's registrations only

### LLM Isolation
- Per-tenant API keys (stored encrypted)
- Per-tenant model configuration
- Per-tenant token budgets and usage tracking

## Rate Limiting

Default limits (configurable per tenant):

| Resource                    | Default Limit      |
|-----------------------------|-------------------|
| API requests                | 1000/min          |
| Workflow executions         | 100/min           |
| Concurrent active sessions  | 100               |
| LLM tokens per day          | 1,000,000         |
| Workflow versions           | 100 per workflow  |

Per-session limits:
- Max steps per execution: 50 (prevents infinite loops)
- Max execution time: 5 minutes
- Max session age: 24 hours

## Autoscaling

Workers scale based on Redis Stream consumer lag via Kubernetes HPA:
- minReplicas: 2
- maxReplicas: 50
- Scale up trigger: >10 pending messages per worker
- Scale up: +5 pods per 60s
- Scale down: -2 pods per 120s (with 300s stabilization)

Control plane scales on CPU utilization:
- minReplicas: 2, maxReplicas: 10
- Target: 70% CPU utilization

## Capacity Planning (1,000 users, 15 msgs/day)

| Metric                      | Value             |
|-----------------------------|-------------------|
| Total messages/day          | 15,000            |
| Peak hour messages          | ~3,000            |
| Peak concurrent sessions    | ~100              |
| LLM calls/day (hybrid)     | ~10,000-15,000    |
| LLM cost/day                | $5-20             |
| Workers needed (peak)       | 5-15              |
| Workers needed (off-peak)   | 2                 |
| PostgreSQL connections      | 20-50             |
| Redis memory                | ~500MB-1GB        |

## Monitoring

### Key Metrics
- redis_stream_pending_messages
- worker_message_processing_duration_seconds
- workflow_execution_duration_seconds (by workflow_slug)
- llm_call_duration_seconds (by model)
- llm_tokens_used_total (by tenant_id, model)
- workflow_step_errors_total (by step_type)
- active_sessions_gauge (by tenant_id)

### Stack
- Prometheus for metrics
- Grafana for dashboards
- Structured JSON logging (stdout, collected by k8s)
- Sentry for error tracking

### Alert Rules
- Stream lag > 100 for > 2 minutes
- Worker error rate > 5%
- LLM provider error rate > 10%
- Tenant approaching token budget (80%, 95%)
- DLQ messages > 0
