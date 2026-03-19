"""Tests for ToolExecutor — routes calls via Tool Gateway."""

import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_tool_executor_routes_via_gateway():
    from flowforge.tools.executor import ToolExecutor

    gw = AsyncMock()
    gw.invoke = AsyncMock(return_value={"ok": True})
    ex = ToolExecutor(gateway_client=gw)

    out = await ex.execute("http://example", {"a": 1})
    assert out == {"ok": True}
    gw.invoke.assert_awaited_once_with("http://example", {"a": 1}, context=None)
