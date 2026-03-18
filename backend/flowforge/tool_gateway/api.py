from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from flowforge.tool_gateway.schemas import ToolCallInvokeRequest, ToolCallInvokeResponse


router = APIRouter()
security = HTTPBearer()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/v1/tool-calls:invoke", response_model=ToolCallInvokeResponse)
async def invoke_tool_call(
    body: ToolCallInvokeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    # Fail-closed: require Authorization header; auth verification and dispatch
    # will be implemented in a follow-up task.
    if not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    raise HTTPException(status_code=501, detail="Tool gateway auth/dispatch not implemented")
