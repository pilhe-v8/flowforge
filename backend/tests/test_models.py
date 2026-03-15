import uuid
import pytest
from sqlalchemy import String, Integer, Boolean, Text, Numeric, DateTime, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from flowforge.models import (
    Base,
    Tenant,
    User,
    Workflow,
    WorkflowVersion,
    Session,
    Execution,
    ExecutionStep,
    ToolRegistration,
    AgentProfile,
    ResponseTemplate,
    TokenUsage,
)


def get_col(model, col_name):
    return model.__table__.c[col_name]


class TestTenantModel:
    def test_table_name(self):
        assert Tenant.__tablename__ == "tenants"

    def test_primary_key_is_uuid(self):
        col = get_col(Tenant, "id")
        assert col.primary_key
        assert isinstance(col.type, UUID)

    def test_slug_is_unique_and_not_nullable(self):
        col = get_col(Tenant, "slug")
        assert not col.nullable
        assert any(
            col.name in [c.name for c in uc.columns]
            for uc in Tenant.__table__.constraints
            if hasattr(uc, "columns")
        )

    def test_config_is_jsonb(self):
        col = get_col(Tenant, "config")
        assert isinstance(col.type, JSONB)

    def test_is_active_has_server_default(self):
        col = get_col(Tenant, "is_active")
        assert col.server_default is not None

    def test_created_at_has_server_default(self):
        col = get_col(Tenant, "created_at")
        assert col.server_default is not None

    def test_updated_at_has_server_default(self):
        col = get_col(Tenant, "updated_at")
        assert col.server_default is not None

    def test_created_at_is_timezone_aware(self):
        col = get_col(Tenant, "created_at")
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True


class TestUserModel:
    def test_table_name(self):
        assert User.__tablename__ == "users"

    def test_tenant_id_foreign_key(self):
        col = get_col(User, "tenant_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert "tenants.id" in str(fks[0].target_fullname)

    def test_role_default_editor(self):
        col = get_col(User, "role")
        assert col.server_default is not None

    def test_email_is_unique(self):
        col = get_col(User, "email")
        assert not col.nullable
        assert any(
            col.name in [c.name for c in uc.columns]
            for uc in User.__table__.constraints
            if hasattr(uc, "columns")
        )

    def test_role_is_not_nullable(self):
        col = get_col(User, "role")
        assert not col.nullable


class TestWorkflowModel:
    def test_table_name(self):
        assert Workflow.__tablename__ == "workflows"

    def test_tenant_slug_unique_constraint(self):
        constraints = [c for c in Workflow.__table__.constraints if hasattr(c, "columns")]
        col_sets = [frozenset(c.name for c in uc.columns) for uc in constraints]
        assert frozenset(["tenant_id", "slug"]) in col_sets

    def test_tenant_id_not_nullable(self):
        col = get_col(Workflow, "tenant_id")
        assert not col.nullable

    def test_name_not_nullable(self):
        col = get_col(Workflow, "name")
        assert not col.nullable


class TestWorkflowVersionModel:
    def test_table_name(self):
        assert WorkflowVersion.__tablename__ == "workflow_versions"

    def test_workflow_id_cascades_on_delete(self):
        col = get_col(WorkflowVersion, "workflow_id")
        fks = list(col.foreign_keys)
        assert any(fk.ondelete == "CASCADE" for fk in fks)

    def test_compilation_errors_jsonb(self):
        col = get_col(WorkflowVersion, "compilation_errors")
        assert isinstance(col.type, JSONB)

    def test_workflow_version_unique_constraint(self):
        constraints = [c for c in WorkflowVersion.__table__.constraints if hasattr(c, "columns")]
        col_sets = [frozenset(c.name for c in uc.columns) for uc in constraints]
        assert frozenset(["workflow_id", "version"]) in col_sets

    def test_status_not_nullable(self):
        col = get_col(WorkflowVersion, "status")
        assert not col.nullable

    def test_status_has_server_default(self):
        col = get_col(WorkflowVersion, "status")
        assert col.server_default is not None

    def test_created_by_is_nullable(self):
        col = get_col(WorkflowVersion, "created_by")
        assert col.nullable


class TestSessionModel:
    def test_table_name(self):
        assert Session.__tablename__ == "sessions"

    def test_workflow_state_jsonb_not_nullable(self):
        col = get_col(Session, "workflow_state")
        assert isinstance(col.type, JSONB)
        assert not col.nullable

    def test_expires_at_has_server_default(self):
        col = get_col(Session, "expires_at")
        assert col.server_default is not None

    def test_step_count_has_server_default(self):
        col = get_col(Session, "step_count")
        assert col.server_default is not None

    def test_tenant_id_not_nullable(self):
        col = get_col(Session, "tenant_id")
        assert not col.nullable


class TestExecutionModel:
    def test_table_name(self):
        assert Execution.__tablename__ == "executions"

    def test_status_not_nullable(self):
        col = get_col(Execution, "status")
        assert not col.nullable

    def test_input_data_jsonb(self):
        col = get_col(Execution, "input_data")
        assert isinstance(col.type, JSONB)

    def test_output_data_jsonb(self):
        col = get_col(Execution, "output_data")
        assert isinstance(col.type, JSONB)

    def test_session_id_foreign_key(self):
        col = get_col(Execution, "session_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert "sessions.id" in str(fks[0].target_fullname)

    def test_status_has_default_queued(self):
        col = get_col(Execution, "status")
        assert col.server_default is not None


class TestExecutionStepModel:
    def test_table_name(self):
        assert ExecutionStep.__tablename__ == "execution_steps"

    def test_execution_id_cascades_on_delete(self):
        col = get_col(ExecutionStep, "execution_id")
        fks = list(col.foreign_keys)
        assert any(fk.ondelete == "CASCADE" for fk in fks)

    def test_metadata_column_exists_in_db(self):
        # The Python attribute is step_metadata but the DB column is "metadata"
        col = get_col(ExecutionStep, "metadata")
        assert isinstance(col.type, JSONB)

    def test_metadata_has_server_default(self):
        col = get_col(ExecutionStep, "metadata")
        assert col.server_default is not None

    def test_step_id_not_nullable(self):
        col = get_col(ExecutionStep, "step_id")
        assert not col.nullable

    def test_status_not_nullable(self):
        col = get_col(ExecutionStep, "status")
        assert not col.nullable


class TestToolRegistrationModel:
    def test_table_name(self):
        assert ToolRegistration.__tablename__ == "tool_registrations"

    def test_tenant_slug_unique(self):
        constraints = [c for c in ToolRegistration.__table__.constraints if hasattr(c, "columns")]
        col_sets = [frozenset(c.name for c in uc.columns) for uc in constraints]
        assert frozenset(["tenant_id", "slug"]) in col_sets

    def test_protocol_not_nullable(self):
        col = get_col(ToolRegistration, "protocol")
        assert not col.nullable

    def test_endpoint_not_nullable(self):
        col = get_col(ToolRegistration, "endpoint")
        assert not col.nullable

    def test_input_schema_jsonb(self):
        col = get_col(ToolRegistration, "input_schema")
        assert isinstance(col.type, JSONB)


class TestAgentProfileModel:
    def test_table_name(self):
        assert AgentProfile.__tablename__ == "agent_profiles"

    def test_guidelines_is_array(self):
        col = get_col(AgentProfile, "guidelines")
        assert isinstance(col.type, ARRAY)

    def test_tenant_slug_unique(self):
        constraints = [c for c in AgentProfile.__table__.constraints if hasattr(c, "columns")]
        col_sets = [frozenset(c.name for c in uc.columns) for uc in constraints]
        assert frozenset(["tenant_id", "slug"]) in col_sets

    def test_content_not_nullable(self):
        col = get_col(AgentProfile, "content")
        assert not col.nullable


class TestResponseTemplateModel:
    def test_table_name(self):
        assert ResponseTemplate.__tablename__ == "response_templates"

    def test_variables_not_nullable_array(self):
        col = get_col(ResponseTemplate, "variables")
        assert isinstance(col.type, ARRAY)
        assert not col.nullable

    def test_tenant_slug_unique(self):
        constraints = [c for c in ResponseTemplate.__table__.constraints if hasattr(c, "columns")]
        col_sets = [frozenset(c.name for c in uc.columns) for uc in constraints]
        assert frozenset(["tenant_id", "slug"]) in col_sets

    def test_content_not_nullable(self):
        col = get_col(ResponseTemplate, "content")
        assert not col.nullable


class TestTokenUsageModel:
    def test_table_name(self):
        assert TokenUsage.__tablename__ == "token_usage"

    def test_cost_usd_numeric(self):
        col = get_col(TokenUsage, "cost_usd")
        assert isinstance(col.type, Numeric)

    def test_model_not_nullable(self):
        col = get_col(TokenUsage, "model")
        assert not col.nullable

    def test_input_tokens_not_nullable(self):
        col = get_col(TokenUsage, "input_tokens")
        assert not col.nullable

    def test_output_tokens_not_nullable(self):
        col = get_col(TokenUsage, "output_tokens")
        assert not col.nullable

    def test_execution_id_is_nullable(self):
        col = get_col(TokenUsage, "execution_id")
        assert col.nullable

    def test_execution_id_foreign_key(self):
        col = get_col(TokenUsage, "execution_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert "executions.id" in str(fks[0].target_fullname)

    def test_tenant_id_foreign_key(self):
        col = get_col(TokenUsage, "tenant_id")
        fks = list(col.foreign_keys)
        assert "tenants.id" in str(fks[0].target_fullname)


class TestAllTablesRegistered:
    def test_all_tables_in_metadata(self):
        expected = {
            "tenants",
            "users",
            "workflows",
            "workflow_versions",
            "sessions",
            "executions",
            "execution_steps",
            "tool_registrations",
            "agent_profiles",
            "response_templates",
            "token_usage",
        }
        actual = set(Base.metadata.tables.keys())
        assert expected == actual

    def test_model_count(self):
        """Ensure exactly 11 tables are registered."""
        assert len(Base.metadata.tables) == 11
