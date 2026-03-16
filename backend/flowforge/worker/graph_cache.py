import pickle

from sqlalchemy import select

from flowforge.compiler import Compiler
from flowforge.db.session import AsyncSessionLocal
from flowforge.models import WorkflowVersion, Workflow


class WorkflowRepo:
    """Data access helper for fetching active workflow YAML definitions."""

    @staticmethod
    async def get_active_yaml(workflow_slug: str, tenant_id: str) -> str:
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
            return model.yaml_definition


class GraphCache:
    """Redis-backed cache for compiled LangGraph workflow graphs."""

    CACHE_TTL = 300  # 5 minutes

    @staticmethod
    async def get_or_compile(redis_client, workflow_slug: str, tenant_id: str):
        cache_key = f"flowforge:graph:{tenant_id}:{workflow_slug}"
        cached = await redis_client.get(cache_key)
        if cached:
            return pickle.loads(cached)

        yaml_def = await WorkflowRepo.get_active_yaml(workflow_slug, tenant_id)
        graph = Compiler(
            tool_catalogue={},
            agent_profiles={},
            tool_executor=None,
            llm_client=None,
            template_engine=None,
            profile_loader=None,
        ).compile(yaml_def)
        await redis_client.setex(cache_key, GraphCache.CACHE_TTL, pickle.dumps(graph.graph))
        return graph.graph
