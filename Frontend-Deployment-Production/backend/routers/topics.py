"""routers/topics.py — GET /topics"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.schemas.models import TopicsResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["topics"])

# ---------------------------------------------------------------------------
# Week 3 path (same convention as services/week3_client.py)
# ---------------------------------------------------------------------------
_DEFAULT_WEEK3_PATH = (
    Path(__file__).resolve().parents[3] / "Multi-Agent-Collaboration"
)
_WEEK3_PATH = Path(
    os.getenv("WEEK3_PROJECT_PATH", str(_DEFAULT_WEEK3_PATH))
).resolve()


def _get_topics_from_registry() -> list[str]:
    """Import Week 3's MATCH_REGISTRY and extract canonical topic strings."""
    import importlib

    saved = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "src" or name.startswith("src.")
    }
    for name in saved:
        del sys.modules[name]

    if str(_WEEK3_PATH) in sys.path:
        sys.path.remove(str(_WEEK3_PATH))
    sys.path.insert(0, str(_WEEK3_PATH))

    try:
        mod = importlib.import_module("src.adapters.match_personas_registry")
        registry = mod.MATCH_REGISTRY
        topics = [info["topic"] for info in registry.values()]
    finally:
        for name in list(sys.modules):
            if name == "src" or name.startswith("src."):
                del sys.modules[name]
        sys.modules.update(saved)

    return topics


@router.get(
    "/topics",
    response_model=TopicsResponse,
    summary="List available discussion topics",
    description=(
        "Returns all pre-configured match topics from Week 3's MATCH_REGISTRY. "
        "The frontend can display these in a dropdown. "
        "Users may also submit any free-text topic via POST /discussions — "
        "the engine will auto-detect the best match."
    ),
)
def get_topics() -> TopicsResponse:
    """Return the list of known discussion topics.

    Errors:
        503 — if the Week 3 module cannot be imported (misconfigured path).
    """
    try:
        topics = _get_topics_from_registry()
        logger.info("topics_requested  count=%d", len(topics))
        return TopicsResponse(topics=topics)
    except Exception as exc:
        logger.error("topics_failed  error=%s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "topics_unavailable",
                "message": (
                    "Could not load topic list from Week 3 module. "
                    f"Check WEEK3_PROJECT_PATH (currently: {_WEEK3_PATH}). "
                    f"Detail: {exc}"
                ),
            },
        ) from exc
