"""Tests for ToolExecutor — routes calls via Tool Gateway."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _isolate_settings_from_dotenv():
    """Keep executor tests independent of a local .env file."""

    from flowforge.config import Settings

    original_env_file = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None
    try:
        yield
    finally:
        if original_env_file is None:
            Settings.model_config.pop("env_file", None)
        else:
            Settings.model_config["env_file"] = original_env_file


@pytest.mark.asyncio
async def test_tool_executor_routes_via_gateway():
    from flowforge.tools.executor import ToolExecutor

    gw = AsyncMock()
    gw.invoke = AsyncMock(return_value={"ok": True})
    ex = ToolExecutor(gateway_client=gw)

    out = await ex.execute("http://example", {"a": 1})
    assert out == {"ok": True}
    gw.invoke.assert_awaited_once_with("http://example", {"a": 1}, context=None)


def test_tool_executor_fail_closed_when_gateway_env_missing(monkeypatch):
    from flowforge.config import get_settings
    from flowforge.tools.executor import ToolExecutor

    monkeypatch.delenv("FLOWFORGE_TOOL_GATEWAY_URL", raising=False)
    monkeypatch.delenv("FLOWFORGE_TOOL_GATEWAY_JWT", raising=False)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match=r"Tool gateway is not configured"):
        ToolExecutor()


@pytest.mark.asyncio
async def test_tool_executor_forwards_context_to_gateway_invoke():
    from flowforge.tools.executor import ToolExecutor

    gw = AsyncMock()
    gw.invoke = AsyncMock(return_value={"ok": True})
    ex = ToolExecutor(gateway_client=gw)

    ctx = {"tenant_id": "t1", "user_id": "u1"}
    out = await ex.execute("http://example", {"a": 1}, context=ctx)

    assert out == {"ok": True}
    gw.invoke.assert_awaited_once_with("http://example", {"a": 1}, context=ctx)


@pytest.mark.asyncio
async def test_tool_executor_sanitizes_gateway_invoke_exception():
    from flowforge.tools.executor import ToolExecutor

    secret = "sk-test-super-secret-token"
    gw = AsyncMock()
    gw.invoke = AsyncMock(side_effect=RuntimeError(f"boom {secret}"))
    ex = ToolExecutor(gateway_client=gw)

    tool_uri = "http://example/tool"
    with pytest.raises(RuntimeError) as excinfo:
        await ex.execute(tool_uri, {"a": 1})

    msg = str(excinfo.value)
    assert tool_uri in msg
    assert secret not in msg
    assert excinfo.value.__cause__ is None
