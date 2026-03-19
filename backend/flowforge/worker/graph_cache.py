import time
from typing import Tuple

from sqlalchemy import select

from flowforge.compiler import Compiler
from flowforge.config import get_settings
from flowforge.db.session import AsyncSessionLocal
from flowforge.models import WorkflowVersion, Workflow
from flowforge.llm.client import LLMClient
from flowforge.tools.executor import ToolExecutor

# In-process TTL cache: key -> (graph, version, expires_at)
_graph_cache: dict[str, tuple[object, int, float]] = {}

# Singleton runtime dependencies shared across all compilations in this process
_tool_executor: ToolExecutor | None = None
_llm_client: LLMClient | None = None


def _get_runtime_deps() -> tuple[ToolExecutor, LLMClient]:
    """Return (or lazily create) the singleton runtime dependency instances.

    These are created once per worker process and reused for every graph
    compilation, ensuring compiled node callables have real clients rather
    than None stubs.
    """
    global _tool_executor, _llm_client
    if _tool_executor is None:
        # Fail-closed: ToolExecutor requires gateway URL/JWT via settings/env.
        _tool_executor = ToolExecutor()
    if _llm_client is None:
        settings = get_settings()
        _llm_client = LLMClient(
            base_url=settings.litellm_url,
            api_key=settings.litellm_master_key,
        )
    return _tool_executor, _llm_client


class WorkflowRepo:
    """Data access helper for fetching active workflow YAML definitions."""

    @staticmethod
    async def get_active_yaml(workflow_slug: str, tenant_id: str) -> Tuple[str, int]:
        async with AsyncSessionLocal() as db:
            # Join WorkflowVersion with Workflow to filter by slug and tenant_id
            row = await db.execute(
                select(WorkflowVersion)
                .join(Workflow, WorkflowVersion.workflow_id == Workflow.id)
                .where(
                    Workflow.slug == workflow_slug,
                    Workflow.tenant_id == tenant_id,
                    WorkflowVersion.status == "active",
                )
                .order_by(WorkflowVersion.version.desc())
                .limit(1)
            )
            model = row.scalar_one_or_none()
            if model is None:
                raise ValueError(
                    f"No active workflow found: {workflow_slug} for tenant {tenant_id}"
                )
            return model.yaml_definition, model.version


class GraphCache:
    """In-process TTL cache for compiled LangGraph workflow graphs."""

    CACHE_TTL = 300  # 5 minutes

    @staticmethod
    async def get_or_compile(
        redis_client, workflow_slug: str, tenant_id: str
    ) -> Tuple[object, int]:
        cache_key = f"{tenant_id}:{workflow_slug}"
        cached = _graph_cache.get(cache_key)
        if cached and time.monotonic() < cached[2]:
            return cached[0], cached[1]

        yaml_def, version = await WorkflowRepo.get_active_yaml(workflow_slug, tenant_id)

        tool_executor, llm_client = _get_runtime_deps()

        result = Compiler(
            tool_catalogue={},
            agent_profiles={},
            tool_executor=tool_executor,
            llm_client=llm_client,
            template_engine=None,
            profile_loader=None,
        ).compile(yaml_def)
        _graph_cache[cache_key] = (result.graph, version, time.monotonic() + GraphCache.CACHE_TTL)
        return result.graph, version
