import json
from typing import Any

import httpx
import pytest


def _client_is_closed(client: httpx.AsyncClient) -> bool:
    # httpx has used both `is_closed` and `closed` across versions.
    if hasattr(client, "is_closed"):
        return bool(getattr(client, "is_closed"))
    return bool(getattr(client, "closed"))


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


@pytest.mark.asyncio
async def test_gateway_client_non_2xx_raises_and_does_not_leak_bearer_token():
    from flowforge.tools.gateway_client import ToolGatewayClient

    jwt_token = "token-SECRET-should-not-leak"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://gw") as client:
        gw = ToolGatewayClient(base_url="http://gw", jwt_token=jwt_token, client=client)
        with pytest.raises(RuntimeError) as e:
            await gw.invoke("mcp://x/y", {"q": "hi"})

    msg = str(e.value)
    assert "(401)" in msg
    assert "mcp://x/y" in msg
    assert jwt_token not in msg
    assert "Bearer" not in msg


@pytest.mark.asyncio
async def test_gateway_client_aclose_closes_owned_client_but_not_injected_client():
    from flowforge.tools.gateway_client import ToolGatewayClient

    gw_owned = ToolGatewayClient(base_url="http://gw", jwt_token="token", client=None)
    try:
        assert not _client_is_closed(gw_owned._client)
        await gw_owned.aclose()
        assert _client_is_closed(gw_owned._client)
    finally:
        await gw_owned.aclose()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output": {"ok": True}})

    transport = httpx.MockTransport(handler)
    injected = httpx.AsyncClient(transport=transport, base_url="http://gw")
    try:
        gw_injected = ToolGatewayClient(base_url="http://gw", jwt_token="token", client=injected)
        assert not _client_is_closed(injected)
        await gw_injected.aclose()
        assert not _client_is_closed(injected)
    finally:
        await injected.aclose()
