from fastapi import APIRouter, Depends, HTTPException
from functools import lru_cache
from uuid import uuid4

from flowforge.tool_gateway.schemas import ToolCallInvokeRequest, ToolCallInvokeResponse
from flowforge.tool_gateway.auth import get_current_user

from flowforge.tools.executor import ToolExecutor
from flowforge.tools.mcp_client import MCPToolClient
from flowforge.tools.http_client import HTTPToolClient


router = APIRouter()


@lru_cache
def get_tool_executor() -> ToolExecutor:
    return ToolExecutor(MCPToolClient(), HTTPToolClient())


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/v1/tool-calls:invoke", response_model=ToolCallInvokeResponse)
async def invoke_tool_call(
    body: ToolCallInvokeRequest,
    user: dict = Depends(get_current_user),
    executor: ToolExecutor = Depends(get_tool_executor),
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
