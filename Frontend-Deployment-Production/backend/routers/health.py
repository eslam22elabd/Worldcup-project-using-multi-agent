"""routers/health.py — GET /health"""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Lightweight liveness probe. Returns HTTP 200 with `{\"status\": \"ok\"}` "
        "whenever the process is running. Makes no LLM or database calls."
    ),
)
def health_check() -> HealthResponse:
    """Return ``{"status": "ok"}`` — no side-effects, no dependencies."""
    return HealthResponse(status="ok")
