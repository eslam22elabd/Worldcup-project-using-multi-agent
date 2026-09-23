"""main.py — FastAPI application entry point.


Running locally
---------------
From the Frontend-Deployment-Production/ directory:

    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.logging_config import setup_logging
from backend.routers import discussions, health, retrieval, topics


from contextlib import asynccontextmanager
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


# ── Initialise logging before anything else touches the root logger ──────────
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_started  version=%s  docs=/docs", app.version)
    yield
    logger.info("app_shutdown")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Multi-Agent Discussion API",
    version="1.0.0",
    description="Backend API for the Multi-Agent Collaboration project.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ── Request / Response logging middleware ────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every incoming request and its response status + duration."""
    start = time.perf_counter()
    logger.info("[request]  %s %s", request.method, request.url.path)

    response = await call_next(request)

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "[response] %s %s -> %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


# ── Global exception handlers ───────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "message": str(exc.detail)},
    )


@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request body failed schema validation.",
            "detail": exc.detail if hasattr(exc, "detail") else str(exc),
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(
        "unhandled_server_error  %s %s  error=%s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


# ── Include routers ───────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(topics.router)
app.include_router(discussions.router)
app.include_router(retrieval.router)


# ── Mount Frontend Static Files if built (Production / Docker) ───────────────
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
