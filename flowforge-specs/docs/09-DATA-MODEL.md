# 09 - Data Model Specification

## Overview

All persistent state lives in PostgreSQL. ORM: SQLAlchemy 2.0 (async).

## Tables

### tenants
```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
-- config keys: default_llm_model, daily_token_budget, max_concurrent_sessions, llm_api_keys (encrypted)
```

### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(300) UNIQUE NOT NULL,
    name VARCHAR(200),
    role VARCHAR(20) NOT NULL DEFAULT 'editor',
    password_hash VARCHAR(200),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_users_tenant ON users(tenant_id);
```

### workflows
```sql
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    slug VARCHAR(200) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, slug)
);
CREATE INDEX idx_workflows_tenant ON workflows(tenant_id);
```

### workflow_versions
```sql
CREATE TABLE workflow_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    yaml_definition TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    trigger_type VARCHAR(50),
    node_count INTEGER,
    compilation_errors JSONB DEFAULT '[]',
    compiled_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(workflow_id, version)
);
CREATE INDEX idx_wv_workflow ON workflow_versions(workflow_id);
CREATE INDEX idx_wv_active ON workflow_versions(status) WHERE status = 'active';
```

### sessions
```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workflow_slug VARCHAR(200) NOT NULL,
    workflow_version INTEGER NOT NULL,
    user_id VARCHAR(200),
    workflow_state JSONB NOT NULL DEFAULT '{}',
    step_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ DEFAULT now() + interval '24 hours'
);
CREATE INDEX idx_sessions_tenant ON sessions(tenant_id);
CREATE INDEX idx_sessions_workflow ON sessions(workflow_slug);
CREATE INDEX idx_sessions_active ON sessions(status) WHERE status = 'active';
CREATE INDEX idx_sessions_expires ON sessions(expires_at) WHERE status = 'active';
```

### executions
```sql
CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    session_id UUID NOT NULL REFERENCES sessions(id),
    workflow_slug VARCHAR(200) NOT NULL,
    workflow_version INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    queued_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    worker_id VARCHAR(100)
);
CREATE INDEX idx_exec_tenant ON executions(tenant_id);
CREATE INDEX idx_exec_session ON executions(session_id);
CREATE INDEX idx_exec_status ON executions(status);
CREATE INDEX idx_exec_queued ON executions(queued_at);
```

### execution_steps
```sql
CREATE TABLE execution_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    step_id VARCHAR(200) NOT NULL,
    step_name VARCHAR(200) NOT NULL,
    step_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX idx_steps_execution ON execution_steps(execution_id);
```

### tool_registrations
```sql
CREATE TABLE tool_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    slug VARCHAR(200) NOT NULL,
    name VARCHAR(200) NOT NULL,
    protocol VARCHAR(20) NOT NULL,
    endpoint VARCHAR(500) NOT NULL,
    description TEXT,
    input_schema JSONB,
    output_schema JSONB,
    auth_config JSONB,
    is_active BOOLEAN DEFAULT true,
    discovered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, slug)
);
CREATE INDEX idx_tools_tenant ON tool_registrations(tenant_id);
```

### agent_profiles
```sql
CREATE TABLE agent_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    slug VARCHAR(200) NOT NULL,
    name VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    role_prompt TEXT,
    guidelines TEXT[],
    output_description TEXT,
    default_model VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, slug)
);
CREATE INDEX idx_agents_tenant ON agent_profiles(tenant_id);
```

### response_templates
```sql
CREATE TABLE response_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    slug VARCHAR(200) NOT NULL,
    name VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    variables TEXT[] NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, slug)
);
```

### token_usage
```sql
CREATE TABLE token_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    execution_id UUID REFERENCES executions(id),
    step_id VARCHAR(200),
    model VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd DECIMAL(10, 6),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_tokens_tenant_date ON token_usage(tenant_id, created_at);
```

## Migrations

Alembic for schema migrations:
```
backend/flowforge/db/migrations/
  env.py
  versions/
    001_initial_schema.py
```

Run: alembic upgrade head

## Session Cleanup (CronJob)

```sql
UPDATE sessions SET status = 'expired'
WHERE status = 'active' AND expires_at < now();
```

## SQLAlchemy Models Example

```python
# backend/flowforge/models/workflow.py

from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid

class Base(DeclarativeBase):
    pass

class Workflow(Base):
    __tablename__ = "workflows"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    slug = Column(String(200), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    versions = relationship("WorkflowVersion", back_populates="workflow")

class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    version = Column(Integer, nullable=False)
    yaml_definition = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    compilation_errors = Column(JSONB, default=[])
    workflow = relationship("Workflow", back_populates="versions")
```
