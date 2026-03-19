"""Tests for GraphCache and WorkflowRepo."""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def _isolate_settings_and_configure_tool_gateway(monkeypatch):
    """Keep worker tests independent of local .env and satisfy fail-closed ToolExecutor."""

    from flowforge.config import Settings, get_settings

    original_env_file = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None

    monkeypatch.setenv("FLOWFORGE_TOOL_GATEWAY_URL", "http://example:9999")
    monkeypatch.setenv("FLOWFORGE_TOOL_GATEWAY_JWT", "test-jwt")
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()
        if original_env_file is None:
            Settings.model_config.pop("env_file", None)
        else:
            Settings.model_config["env_file"] = original_env_file


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
    def setup_method(self):
        """Clear the in-process cache before each test."""
        from flowforge.worker import graph_cache

        graph_cache._graph_cache.clear()
        graph_cache._tool_executor = None
        graph_cache._llm_client = None

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_graph(self):
        """get_or_compile should return cached (graph, version) on cache hit."""
        from flowforge.worker.graph_cache import GraphCache, _graph_cache

        fake_graph = {"nodes": ["trigger", "step1"], "compiled": True}
        cache_key = "t-001:my-wf"
        _graph_cache[cache_key] = (fake_graph, 42, time.monotonic() + 300)

        redis_client = AsyncMock()

        result_graph, result_version = await GraphCache.get_or_compile(
            redis_client, "my-wf", "t-001"
        )

        # Redis should NOT be called at all (in-process cache only)
        redis_client.get.assert_not_called()
        assert result_graph == fake_graph
        assert result_version == 42

    @pytest.mark.asyncio
    async def test_cache_miss_compiles_and_caches(self):
        """get_or_compile should compile from YAML and store in in-process cache on miss."""
        from flowforge.worker.graph_cache import GraphCache, _graph_cache

        fake_graph = {"nodes": ["trigger"], "compiled": True}
        fake_compilation = MagicMock()
        fake_compilation.graph = fake_graph

        redis_client = AsyncMock()

        with patch(
            "flowforge.worker.graph_cache.WorkflowRepo.get_active_yaml",
            new=AsyncMock(return_value=("workflow: yaml", 7)),
        ):
            with patch(
                "flowforge.worker.graph_cache.Compiler",
            ) as MockCompiler:
                mock_compiler_instance = MagicMock()
                mock_compiler_instance.compile.return_value = fake_compilation
                MockCompiler.return_value = mock_compiler_instance

                result_graph, result_version = await GraphCache.get_or_compile(
                    redis_client, "slug", "tenant-1"
                )

        # Should have stored in the in-process cache
        assert "tenant-1:slug" in _graph_cache
        cached_graph, cached_version, expires_at = _graph_cache["tenant-1:slug"]
        assert cached_graph == fake_graph
        assert cached_version == 7
        assert expires_at > time.monotonic()

        # Should return the compiled graph and version
        assert result_graph == fake_graph
        assert result_version == 7

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_yaml_from_repo(self):
        """get_or_compile should call WorkflowRepo.get_active_yaml on cache miss."""
        from flowforge.worker.graph_cache import GraphCache

        redis_client = AsyncMock()

        fake_graph = {"nodes": [], "compiled": True}
        fake_compilation = MagicMock()
        fake_compilation.graph = fake_graph

        mock_get_yaml = AsyncMock(return_value=("workflow: def", 3))

        with patch("flowforge.worker.graph_cache.WorkflowRepo.get_active_yaml", mock_get_yaml):
            with patch("flowforge.worker.graph_cache.Compiler") as MockCompiler:
                MockCompiler.return_value.compile.return_value = fake_compilation
                await GraphCache.get_or_compile(redis_client, "wf-slug", "t-id")

        mock_get_yaml.assert_awaited_once_with("wf-slug", "t-id")

    @pytest.mark.asyncio
    async def test_expired_cache_entry_is_recompiled(self):
        """get_or_compile should recompile when a cache entry has expired."""
        from flowforge.worker.graph_cache import GraphCache, _graph_cache

        old_graph = {"nodes": ["old"], "compiled": True}
        cache_key = "t-exp:wf-exp"
        # Insert an already-expired entry
        _graph_cache[cache_key] = (old_graph, 1, time.monotonic() - 1)

        new_graph = {"nodes": ["new"], "compiled": True}
        fake_compilation = MagicMock()
        fake_compilation.graph = new_graph

        redis_client = AsyncMock()

        with patch(
            "flowforge.worker.graph_cache.WorkflowRepo.get_active_yaml",
            new=AsyncMock(return_value=("workflow: new", 2)),
        ):
            with patch("flowforge.worker.graph_cache.Compiler") as MockCompiler:
                MockCompiler.return_value.compile.return_value = fake_compilation
                result_graph, result_version = await GraphCache.get_or_compile(
                    redis_client, "wf-exp", "t-exp"
                )

        assert result_graph == new_graph
        assert result_version == 2


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
    async def test_get_active_yaml_returns_yaml_definition_and_version(self):
        """get_active_yaml should return (yaml_definition, version) tuple from the model."""
        from flowforge.worker.graph_cache import WorkflowRepo

        model = MagicMock()
        model.yaml_definition = "name: test-workflow\nsteps: []"
        model.version = 5

        db = make_db_with_result(model)
        ctx = FakeAsyncContextManager(db)

        with patch("flowforge.worker.graph_cache.AsyncSessionLocal", return_value=ctx):
            yaml_def, version = await WorkflowRepo.get_active_yaml("test-wf", "t-abc")

        assert yaml_def == "name: test-workflow\nsteps: []"
        assert version == 5

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
