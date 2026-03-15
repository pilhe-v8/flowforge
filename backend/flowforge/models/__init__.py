from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    Text,
    ForeignKey,
    Numeric,
    ARRAY,
    UniqueConstraint,
    DateTime,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# Timezone-aware timestamp type (maps to TIMESTAMPTZ in PostgreSQL)
TZ = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
    workflows: Mapped[list["Workflow"]] = relationship("Workflow", back_populates="tenant")
    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="tenant")
    executions: Mapped[list["Execution"]] = relationship("Execution", back_populates="tenant")
    tool_registrations: Mapped[list["ToolRegistration"]] = relationship(
        "ToolRegistration", back_populates="tenant"
    )
    agent_profiles: Mapped[list["AgentProfile"]] = relationship(
        "AgentProfile", back_populates="tenant"
    )
    response_templates: Mapped[list["ResponseTemplate"]] = relationship(
        "ResponseTemplate", back_populates="tenant"
    )
    token_usages: Mapped[list["TokenUsage"]] = relationship("TokenUsage", back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'editor'"))
    password_hash: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    workflow_versions: Mapped[list["WorkflowVersion"]] = relationship(
        "WorkflowVersion", back_populates="created_by_user"
    )


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="workflows")
    versions: Mapped[list["WorkflowVersion"]] = relationship(
        "WorkflowVersion", back_populates="workflow"
    )


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    yaml_definition: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    trigger_type: Mapped[Optional[str]] = mapped_column(String(50))
    node_count: Mapped[Optional[int]] = mapped_column(Integer)
    compilation_errors: Mapped[Optional[list]] = mapped_column(JSONB, server_default=text("'[]'"))
    compiled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("workflow_id", "version"),)

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="versions")
    created_by_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="workflow_versions"
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    workflow_slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(200))
    workflow_state: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    step_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("0"))
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'active'"))
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now() + interval '24 hours'"),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="sessions")
    executions: Mapped[list["Execution"]] = relationship("Execution", back_populates="session")


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, index=True
    )
    workflow_slug: Mapped[str] = mapped_column(String(200), nullable=False)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'queued'"))
    input_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    queued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    worker_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="executions")
    session: Mapped["Session"] = relationship("Session", back_populates="executions")
    steps: Mapped[list["ExecutionStep"]] = relationship("ExecutionStep", back_populates="execution")
    token_usages: Mapped[list["TokenUsage"]] = relationship(
        "TokenUsage", back_populates="execution"
    )


class ExecutionStep(Base):
    __tablename__ = "execution_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id: Mapped[str] = mapped_column(String(200), nullable=False)
    step_name: Mapped[str] = mapped_column(String(200), nullable=False)
    step_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    # Named "step_metadata" in Python to avoid conflict with SQLAlchemy's DeclarativeBase.metadata
    step_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'")
    )

    # Relationships
    execution: Mapped["Execution"] = relationship("Execution", back_populates="steps")


class ToolRegistration(Base):
    __tablename__ = "tool_registrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    input_schema: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_schema: Mapped[Optional[dict]] = mapped_column(JSONB)
    auth_config: Mapped[Optional[dict]] = mapped_column(JSONB)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text("true"))
    discovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="tool_registrations")


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    role_prompt: Mapped[Optional[str]] = mapped_column(Text)
    guidelines: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    output_description: Mapped[Optional[str]] = mapped_column(Text)
    default_model: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="agent_profiles")


class ResponseTemplate(Base):
    __tablename__ = "response_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(ARRAY(Text), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="response_templates")


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("executions.id"), nullable=True
    )
    step_id: Mapped[Optional[str]] = mapped_column(String(200))
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6))
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="token_usages")
    execution: Mapped[Optional["Execution"]] = relationship(
        "Execution", back_populates="token_usages"
    )

    __table_args__ = (Index("idx_tokens_tenant_date", "tenant_id", "created_at"),)


__all__ = [
    "Base",
    "Tenant",
    "User",
    "Workflow",
    "WorkflowVersion",
    "Session",
    "Execution",
    "ExecutionStep",
    "ToolRegistration",
    "AgentProfile",
    "ResponseTemplate",
    "TokenUsage",
]
