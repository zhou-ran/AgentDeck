from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.auth import require_token
from backend.api.processes import router as processes_router
from backend.api.sse import router as sse_router
from backend.api.tasks import router as tasks_router
from backend.config import get_host, get_port
from backend.security import api_rate_limiter, init_allowed_dirs

logger = logging.getLogger("agentdeck")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize security: allowed dirs for log reads
    init_allowed_dirs()
    # Prime psutil cpu_percent (first call returns 0)
    import psutil
    psutil.cpu_percent(interval=0)

    async def cleanup_rate_limiter() -> None:
        while True:
            await asyncio.sleep(60)
            api_rate_limiter.cleanup()

    cleanup_task = asyncio.create_task(cleanup_rate_limiter())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(
    title="AgentDeck",
    description="Local coding agent monitoring dashboard",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — restrict to localhost origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://localhost",
        "http://127.0.0.1:9797",
        "http://localhost:9797",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# --- Security middleware ---

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Rate limiting by client IP
    client_ip = request.client.host if request.client else "unknown"
    if not api_rate_limiter.is_allowed(client_ip):
        return Response(content="Rate limit exceeded", status_code=429)

    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'"
    )
    return response


# Mount API routers — all require authentication
app.include_router(tasks_router, prefix="/api", dependencies=[require_token()])
app.include_router(processes_router, prefix="/api", dependencies=[require_token()])
app.include_router(sse_router, prefix="/api", dependencies=[require_token()])


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def api_not_found(path: str):
    return Response(
        content='{"detail":"Not Found"}',
        status_code=404,
        media_type="application/json",
    )


# Serve frontend static files (built by Vite)
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")


def run_server(host: str | None = None, port: int | None = None):
    import uvicorn
    h = host or get_host()
    p = port or get_port()

    # Security warning for non-localhost binding
    if h not in ("127.0.0.1", "localhost", "::1"):
        from backend.security import get_token
        token = get_token()
        print("\n" + "=" * 60, file=sys.stderr)
        print("  WARNING: AgentDeck is listening on ALL interfaces!", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"  Address: http://{h}:{p}", file=sys.stderr)
        print(f"  Token:   {token}", file=sys.stderr)
        print("", file=sys.stderr)
        print("  Anyone on your network can access this dashboard.", file=sys.stderr)
        print("  Use the Bearer token above to authenticate.", file=sys.stderr)
        print("", file=sys.stderr)
        print("  To bind to localhost only:", file=sys.stderr)
        print("    agentdeck serve --host 127.0.0.1", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)

    uvicorn.run(app, host=h, port=p, log_level="info")


if __name__ == "__main__":
    run_server()
