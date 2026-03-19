import logging
from fastapi import APIRouter, Depends, HTTPException
from functools import lru_cache
from uuid import uuid4

from flowforge.tool_gateway.schemas import ToolCallInvokeRequest, ToolCallInvokeResponse
from flowforge.tool_gateway.auth import get_current_user

from flowforge.tools.mcp_client import MCPToolClient
from flowforge.tools.http_client import HTTPToolClient


router = APIRouter()
logger = logging.getLogger(__name__)


@lru_cache
def get_mcp_client() -> MCPToolClient:
    return MCPToolClient()


@lru_cache
def get_http_client() -> HTTPToolClient:
    return HTTPToolClient()


class ToolDispatcher:
    async def execute(self, tool_uri: str, inputs: dict, auth: dict | None = None) -> dict:
        _ = auth

        if tool_uri == "log":
            logger.info("tool-gateway log tool: %s", inputs)
            return {"ok": True}

        if tool_uri.startswith("mcp://"):
            return await get_mcp_client().call(tool_uri, inputs)

        if tool_uri.startswith("http://") or tool_uri.startswith("https://"):
            return await get_http_client().call(tool_uri, inputs, auth=None)

        raise ValueError(f"Unknown protocol in URI: {tool_uri}")


@lru_cache
def get_tool_executor() -> ToolDispatcher:
    return ToolDispatcher()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/v1/tool-calls:invoke", response_model=ToolCallInvokeResponse)
async def invoke_tool_call(
    body: ToolCallInvokeRequest,
    user: dict = Depends(get_current_user),
    executor: ToolDispatcher = Depends(get_tool_executor),
):
    _ = user
    try:
        result = await executor.execute(body.tool_uri, body.inputs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="Tool execution failed")

    return ToolCallInvokeResponse(
        status="completed",
        tool_call_id=str(uuid4()),
        output=result,
    )
