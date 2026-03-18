from fastapi import FastAPI

from flowforge.tool_gateway.api import router


app = FastAPI(title="FlowForge Tool Gateway", version="0.1.0")
app.include_router(router)
