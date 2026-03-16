"""Tests for GraphCache and WorkflowRepo."""

import pickle
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class FakeAsyncContextManager:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        pass


def make_db_with_result(result):
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = result
    db.execute = AsyncMock(return_value=execute_result)
    return db


# ── GraphCache ────────────────────────────────────────────────────────────────


class TestGraphCache:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_deserialized_graph(self):
        """get_or_compile should return the pickle-deserialized graph on cache hit."""
        from flowforge.worker.graph_cache import GraphCache

        # Use a simple picklable object as a fake graph
        fake_graph = {"nodes": ["trigger", "step1"], "compiled": True}
        cached_bytes = pickle.dumps(fake_graph)

        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=cached_bytes)

        result = await GraphCache.get_or_compile(redis_client, "my-wf", "t-001")

        redis_client.get.assert_awaited_once_with("flowforge:graph:t-001:my-wf")
        assert result == fake_graph

    @pytest.mark.asyncio
    async def test_cache_miss_compiles_and_caches(self):
        """get_or_compile should compile from YAML and store in Redis on cache miss."""
        from flowforge.worker.graph_cache import GraphCache

        # Use a simple picklable object as a fake graph
        fake_graph = {"nodes": ["trigger"], "compiled": True}
        fake_compilation = MagicMock()
        fake_compilation.graph = fake_graph

        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.setex = AsyncMock()

        with patch(
            "flowforge.worker.graph_cache.WorkflowRepo.get_active_yaml",
            new=AsyncMock(return_value="workflow: yaml"),
        ):
            with patch(
                "flowforge.worker.graph_cache.Compiler",
            ) as MockCompiler:
                mock_compiler_instance = MagicMock()
                mock_compiler_instance.compile.return_value = fake_compilation
                MockCompiler.return_value = mock_compiler_instance

                result = await GraphCache.get_or_compile(redis_client, "slug", "tenant-1")

        # Should have cached the pickled graph
        redis_client.setex.assert_awaited_once()
        args = redis_client.setex.call_args[0]
        assert args[0] == "flowforge:graph:tenant-1:slug"
        assert args[1] == GraphCache.CACHE_TTL
        assert pickle.loads(args[2]) == fake_graph

        # Should return the compiled graph
        assert result == fake_graph

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_yaml_from_repo(self):
        """get_or_compile should call WorkflowRepo.get_active_yaml on cache miss."""
        from flowforge.worker.graph_cache import GraphCache

        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.setex = AsyncMock()

        fake_graph = {"nodes": [], "compiled": True}
        fake_compilation = MagicMock()
        fake_compilation.graph = fake_graph

        mock_get_yaml = AsyncMock(return_value="workflow: def")

        with patch("flowforge.worker.graph_cache.WorkflowRepo.get_active_yaml", mock_get_yaml):
            with patch("flowforge.worker.graph_cache.Compiler") as MockCompiler:
                MockCompiler.return_value.compile.return_value = fake_compilation
                await GraphCache.get_or_compile(redis_client, "wf-slug", "t-id")

        mock_get_yaml.assert_awaited_once_with("wf-slug", "t-id")


# ── WorkflowRepo ──────────────────────────────────────────────────────────────


class TestWorkflowRepo:
    @pytest.mark.asyncio
    async def test_get_active_yaml_raises_when_not_found(self):
        """get_active_yaml should raise ValueError when no active workflow is found."""
        from flowforge.worker.graph_cache import WorkflowRepo

        db = make_db_with_result(None)
        ctx = FakeAsyncContextManager(db)

        with patch("flowforge.worker.graph_cache.AsyncSessionLocal", return_value=ctx):
            with pytest.raises(ValueError, match="No active workflow found"):
                await WorkflowRepo.get_active_yaml("missing-wf", "t-001")

    @pytest.mark.asyncio
    async def test_get_active_yaml_returns_yaml_definition(self):
        """get_active_yaml should return the yaml_definition from the model."""
        from flowforge.worker.graph_cache import WorkflowRepo

        model = MagicMock()
        model.yaml_definition = "name: test-workflow\nsteps: []"

        db = make_db_with_result(model)
        ctx = FakeAsyncContextManager(db)

        with patch("flowforge.worker.graph_cache.AsyncSessionLocal", return_value=ctx):
            result = await WorkflowRepo.get_active_yaml("test-wf", "t-abc")

        assert result == "name: test-workflow\nsteps: []"

    @pytest.mark.asyncio
    async def test_get_active_yaml_error_message_contains_slug_and_tenant(self):
        """ValueError message should mention both workflow_slug and tenant_id."""
        from flowforge.worker.graph_cache import WorkflowRepo

        db = make_db_with_result(None)
        ctx = FakeAsyncContextManager(db)

        with patch("flowforge.worker.graph_cache.AsyncSessionLocal", return_value=ctx):
            with pytest.raises(ValueError) as exc_info:
                await WorkflowRepo.get_active_yaml("my-slug", "my-tenant")

        assert "my-slug" in str(exc_info.value)
        assert "my-tenant" in str(exc_info.value)
