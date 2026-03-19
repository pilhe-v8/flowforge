import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_gateway_client_posts_to_invoke_with_bearer_token():
    from flowforge.tools.gateway_client import ToolGatewayClient

    seen: dict[str, object] = {}

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
