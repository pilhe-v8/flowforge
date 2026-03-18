from fastapi import APIRouter, Depends, HTTPException

from flowforge.tool_gateway.schemas import ToolCallInvokeRequest, ToolCallInvokeResponse
from flowforge.tool_gateway.auth import get_current_user


router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/v1/tool-calls:invoke", response_model=ToolCallInvokeResponse)
async def invoke_tool_call(
    body: ToolCallInvokeRequest,
    user: dict = Depends(get_current_user),
):
    # Auth verified; dispatch will be implemented in a follow-up task.
    raise HTTPException(status_code=501, detail="Tool gateway auth/dispatch not implemented")
