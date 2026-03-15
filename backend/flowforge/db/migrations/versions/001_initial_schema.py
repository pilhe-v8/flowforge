"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-03-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tenants
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # users
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("email", sa.String(300), nullable=False, unique=True),
        sa.Column("name", sa.String(200)),
        sa.Column("role", sa.String(20), nullable=False, server_default=sa.text("'editor'")),
        sa.Column("password_hash", sa.String(200)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_users_tenant", "users", ["tenant_id"])

    # workflows
    op.create_table(
        "workflows",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "slug"),
    )
    op.create_index("idx_workflows_tenant", "workflows", ["tenant_id"])

    # workflow_versions
    op.create_table(
        "workflow_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("yaml_definition", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("trigger_type", sa.String(50)),
        sa.Column("node_count", sa.Integer()),
        sa.Column(
            "compilation_errors",
            postgresql.JSONB(),
            server_default=sa.text("'[]'"),
        ),
        sa.Column("compiled_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("workflow_id", "version"),
    )
    op.create_index("idx_wv_workflow", "workflow_versions", ["workflow_id"])
    op.create_index(
        "idx_wv_active",
        "workflow_versions",
        ["status"],
        postgresql_where=sa.text("status = 'active'"),
    )

    # sessions
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("workflow_slug", sa.String(200), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(200)),
        sa.Column(
            "workflow_state",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("step_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("status", sa.String(20), server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now() + interval '24 hours'"),
        ),
    )
    op.create_index("idx_sessions_tenant", "sessions", ["tenant_id"])
    op.create_index("idx_sessions_workflow", "sessions", ["workflow_slug"])
    op.create_index(
        "idx_sessions_active",
        "sessions",
        ["status"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "idx_sessions_expires",
        "sessions",
        ["expires_at"],
        postgresql_where=sa.text("status = 'active'"),
    )

    # executions
    op.create_table(
        "executions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id"),
            nullable=False,
        ),
        sa.Column("workflow_slug", sa.String(200), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("input_data", postgresql.JSONB()),
        sa.Column("output_data", postgresql.JSONB()),
        sa.Column("error_message", sa.Text()),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("worker_id", sa.String(100)),
    )
    op.create_index("idx_exec_tenant", "executions", ["tenant_id"])
    op.create_index("idx_exec_session", "executions", ["session_id"])
    op.create_index("idx_exec_status", "executions", ["status"])
    op.create_index("idx_exec_queued", "executions", ["queued_at"])

    # execution_steps
    op.create_table(
        "execution_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_id", sa.String(200), nullable=False),
        sa.Column("step_name", sa.String(200), nullable=False),
        sa.Column("step_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("input_data", postgresql.JSONB()),
        sa.Column("output_data", postgresql.JSONB()),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'")),
    )
    op.create_index("idx_steps_execution", "execution_steps", ["execution_id"])

    # tool_registrations
    op.create_table(
        "tool_registrations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("protocol", sa.String(20), nullable=False),
        sa.Column("endpoint", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("input_schema", postgresql.JSONB()),
        sa.Column("output_schema", postgresql.JSONB()),
        sa.Column("auth_config", postgresql.JSONB()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("discovered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "slug"),
    )
    op.create_index("idx_tools_tenant", "tool_registrations", ["tenant_id"])

    # agent_profiles
    op.create_table(
        "agent_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("role_prompt", sa.Text()),
        sa.Column("guidelines", postgresql.ARRAY(sa.Text())),
        sa.Column("output_description", sa.Text()),
        sa.Column("default_model", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "slug"),
    )
    op.create_index("idx_agents_tenant", "agent_profiles", ["tenant_id"])

    # response_templates
    op.create_table(
        "response_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("variables", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "slug"),
    )

    # token_usage
    op.create_table(
        "token_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("executions.id"),
            nullable=True,
        ),
        sa.Column("step_id", sa.String(200)),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 6)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_tokens_tenant_date", "token_usage", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("token_usage")
    op.drop_table("response_templates")
    op.drop_table("agent_profiles")
    op.drop_table("tool_registrations")
    op.drop_table("execution_steps")
    op.drop_table("executions")
    op.drop_table("sessions")
    op.drop_table("workflow_versions")
    op.drop_table("workflows")
    op.drop_table("users")
    op.drop_table("tenants")
