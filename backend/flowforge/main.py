from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from flowforge.api import workflows, tools, agents, executions, tenants, webhooks, ws, templates
from flowforge.config import get_settings

settings = get_settings()

app = FastAPI(title="FlowForge", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflows.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(executions.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(ws.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")

Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health():
    return {"status": "ok"}
