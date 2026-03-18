from pydantic import BaseModel


class ToolCallActor(BaseModel):
    sub: str | None = None
    role: str | None = None


class ToolCallContext(BaseModel):
    tenant_id: str | None = None
    workflow_id: str | None = None
    execution_id: str | None = None
    step_id: str | None = None
    actor: ToolCallActor | None = None


class ToolCallInvokeRequest(BaseModel):
    tool_uri: str
    inputs: dict
    context: ToolCallContext | None = None


class ToolCallError(BaseModel):
    code: str
    message: str


class ToolCallInvokeResponse(BaseModel):
    status: str
    tool_call_id: str
    output: dict | None = None
    error: ToolCallError | None = None
