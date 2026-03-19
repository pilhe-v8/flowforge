import json
from typing import Any

import httpx
import pytest


@pytest.mark.asyncio
async def test_gateway_client_posts_to_invoke_with_bearer_token():
    from flowforge.tools.gateway_client import ToolGatewayClient

    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("Authorization")
        seen["json"] = json.loads((await request.aread()).decode("utf-8"))
        return httpx.Response(
            200,
            json={"status": "completed", "tool_call_id": "t1", "output": {"ok": True}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://gw") as client:
        gw = ToolGatewayClient(base_url="http://gw", jwt_token="token", client=client)
        out = await gw.invoke(
            "mcp://x/y",
            {"q": "hi"},
            context={"actor": {"sub": "svc"}},
        )

    assert out == {"ok": True}
    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/tool-calls:invoke"
    assert seen["auth"] == "Bearer token"
    assert isinstance(seen["json"], dict)
    assert seen["json"]["tool_uri"] == "mcp://x/y"
    assert seen["json"]["inputs"] == {"q": "hi"}
    assert seen["json"]["context"] == {"actor": {"sub": "svc"}}


@pytest.mark.asyncio
async def test_gateway_client_payload_includes_inputs_and_context_when_provided():
    from flowforge.tools.gateway_client import ToolGatewayClient

    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["json"] = json.loads((await request.aread()).decode("utf-8"))
        return httpx.Response(200, json={"output": {"ok": True}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://gw") as client:
        gw = ToolGatewayClient(base_url="http://gw", jwt_token="token", client=client)
        await gw.invoke("mcp://x/y", {"q": "hi"}, context={"actor": {"sub": "svc"}})

    assert seen["json"] == {
        "tool_uri": "mcp://x/y",
        "inputs": {"q": "hi"},
        "context": {"actor": {"sub": "svc"}},
    }


@pytest.mark.asyncio
async def test_gateway_client_payload_omits_context_when_none():
    from flowforge.tools.gateway_client import ToolGatewayClient

    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["json"] = json.loads((await request.aread()).decode("utf-8"))
        return httpx.Response(200, json={"output": {"ok": True}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://gw") as client:
        gw = ToolGatewayClient(base_url="http://gw", jwt_token="token", client=client)
        await gw.invoke("mcp://x/y", {"q": "hi"}, context=None)

    assert isinstance(seen["json"], dict)
    assert "context" not in seen["json"]
    assert seen["json"]["inputs"] == {"q": "hi"}


@pytest.mark.asyncio
async def test_gateway_client_output_none_returns_empty_dict():
    from flowforge.tools.gateway_client import ToolGatewayClient

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output": None})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://gw") as client:
        gw = ToolGatewayClient(base_url="http://gw", jwt_token="token", client=client)
        out = await gw.invoke("mcp://x/y", {"q": "hi"})

    assert out == {}


@pytest.mark.asyncio
async def test_gateway_client_output_can_be_falsy_and_is_returned_as_is():
    from flowforge.tools.gateway_client import ToolGatewayClient

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output": 0})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://gw") as client:
        gw = ToolGatewayClient(base_url="http://gw", jwt_token="token", client=client)
        out = await gw.invoke("mcp://x/y", {"q": "hi"})

    assert out == 0


@pytest.mark.asyncio
async def test_gateway_client_non_json_200_raises_clear_error():
    from flowforge.tools.gateway_client import ToolGatewayClient

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://gw") as client:
        gw = ToolGatewayClient(base_url="http://gw", jwt_token="token", client=client)
        with pytest.raises(RuntimeError) as e:
            await gw.invoke("mcp://x/y", {"q": "hi"})

    assert "non-JSON" in str(e.value)
    assert "(200)" in str(e.value)
    assert "mcp://x/y" in str(e.value)
