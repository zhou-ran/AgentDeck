from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.auth import require_token
from backend.api.processes import router as processes_router
from backend.api.sse import router as sse_router
from backend.api.tasks import router as tasks_router
from backend.config import get_host, get_port


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Prime psutil cpu_percent (first call returns 0)
    import psutil
    psutil.cpu_percent(interval=0)
    yield


app = FastAPI(
    title="AgentStatus",
    description="Local coding agent monitoring dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow localhost and LAN origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(tasks_router, prefix="/api", dependencies=[require_token()])
app.include_router(processes_router, prefix="/api", dependencies=[require_token()])
app.include_router(sse_router, prefix="/api")

# Serve frontend static files (built by Vite)
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")


def run_server(host: str | None = None, port: int | None = None):
    import uvicorn
    h = host or get_host()
    p = port or get_port()
    uvicorn.run(app, host=h, port=p, log_level="info")


if __name__ == "__main__":
    run_server()
