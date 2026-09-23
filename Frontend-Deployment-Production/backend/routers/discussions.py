"""routers/discussions.py — Discussion endpoints.

Endpoints
---------
POST /discussions
    Start and run a new multi-agent discussion (calls Week 3 engine).
    Returns once all rounds complete (synchronous — may take ~1-2 min).

GET /discussions/{discussion_id}
    Retrieve a saved discussion from Week 3's DiscussionStore.

GET /discussions/{discussion_id}/analytics
    Compute / return analytics for a completed discussion (calls Week 4 engine).

Error codes
------------------------
400 — invalid / empty topic
404 — discussion_id not found
503 — Week 3 or Week 4 engine unavailable
500 — unexpected server error

Logging
------------------------
Every create + analytics request is logged at INFO level with its id.
Failures are logged at ERROR with id + error message.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.schemas.models import (
    AgentMessage,
    AnalyticsResponse,
    CreateDiscussionRequest,
    CreateDiscussionResponse,
    DiscussionResponse,
    Round,
)
from backend.services import week3_client, week4_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discussions", tags=["discussions"])


# ---------------------------------------------------------------------------
# POST /discussions — Start a new discussion
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=CreateDiscussionResponse,
    status_code=201,
    summary="Start a new multi-agent discussion",
    description=(
        "Runs a complete 3-round discussion using Week 3's engine. "
        "The topic can be a free-text match description in Arabic or English — "
        "the engine auto-detects the best persona set. "
        "**This is a synchronous call; it may take 1-3 minutes while the LLM agents respond.**"
    ),
)
def create_discussion(body: CreateDiscussionRequest) -> CreateDiscussionResponse:
    """Run a new discussion and persist it."""
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_topic",
                "message": "Topic must be a non-empty string.",
            },
        )

    logger.info("discussion_starting  topic=%r", topic)

    result = week3_client.start_discussion(topic)

    if not result.success:
        logger.error(
            "discussion_failed  topic=%r  error=%s", topic, result.error
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "discussion_engine_failed",
                "message": (
                    "The Week 3 discussion engine returned an error. "
                    f"Detail: {result.error}"
                ),
            },
        )

    logger.info(
        "discussion_created  id=%s  topic=%r  agents=%s",
        result.discussion_id,
        result.topic,
        result.agents,
    )

    return CreateDiscussionResponse(
        discussion_id=result.discussion_id,
        status=result.status,
        topic=result.topic,
        agents=result.agents,
        num_rounds=result.num_rounds,
    )


# ---------------------------------------------------------------------------
# GET /discussions/{discussion_id} — Retrieve a discussion
# ---------------------------------------------------------------------------

@router.get(
    "/{discussion_id}",
    response_model=DiscussionResponse,
    summary="Get a discussion by ID",
    description=(
        "Returns the full discussion record: participants, all rounds, "
        "and every agent message.  The discussion must have been created "
        "via POST /discussions first."
    ),
)
def get_discussion(discussion_id: str) -> DiscussionResponse:
    """Load and return a saved discussion."""
    logger.info("discussion_requested  id=%s", discussion_id)

    data = week3_client.load_discussion(discussion_id)

    if data is None:
        logger.error("discussion_not_found  id=%s", discussion_id)
        raise HTTPException(
            status_code=404,
            detail={
                "error": "discussion_not_found",
                "message": f"No discussion found with id '{discussion_id}'.",
            },
        )

    # Build rounds from flat message list or structured rounds dict/list
    flat_messages = list(data.get("messages", []))
    if not flat_messages and "rounds" in data:
        r_raw = data["rounds"]
        if isinstance(r_raw, dict):
            for r_key, r_val in r_raw.items():
                rn_clean = str(r_key).replace("round_", "")
                rn = int(rn_clean) if rn_clean.isdigit() else 1
                msgs = r_val.get("messages", []) if isinstance(r_val, dict) else r_val
                for m in msgs:
                    m_copy = dict(m)
                    m_copy["round"] = m_copy.get("round", rn)
                    flat_messages.append(m_copy)
        elif isinstance(r_raw, list):
            for r_val in r_raw:
                rn = r_val.get("round", 1) if isinstance(r_val, dict) else 1
                msgs = r_val.get("messages", []) if isinstance(r_val, dict) else r_val
                for m in msgs:
                    m_copy = dict(m)
                    m_copy["round"] = m_copy.get("round", rn)
                    flat_messages.append(m_copy)

    rounds_by_number: dict[int, list[AgentMessage]] = {}
    for msg in flat_messages:
        rn = msg.get("round", 1)
        rounds_by_number.setdefault(rn, []).append(
            AgentMessage(
                agent=msg.get("sender", msg.get("sender_id", msg.get("agent", ""))),
                text=msg.get("content", msg.get("text", "")),
                message_id=msg.get("id", msg.get("message_id", "")),
                timestamp=msg.get("timestamp", ""),
            )
        )

    rounds = [
        Round(round=rn, messages=msgs)
        for rn, msgs in sorted(rounds_by_number.items())
    ]

    return DiscussionResponse(
        discussion_id=data["discussion_id"],
        topic=data.get("topic", ""),
        status=data.get("status", ""),
        agents=data.get("participants", []),
        num_rounds=data.get("num_rounds", 0),
        rounds=rounds,
        started_at=data.get("started_at", ""),
        completed_at=data.get("completed_at"),
        termination_reason=data.get("termination_reason", ""),
    )


# ---------------------------------------------------------------------------
# GET /discussions/{discussion_id}/analytics — Compute analytics
# ---------------------------------------------------------------------------

@router.get(
    "/{discussion_id}/analytics",
    response_model=AnalyticsResponse,
    summary="Get analytics for a discussion",
    description=(
        "Runs Week 4's analytics engine on the saved discussion export. "
        "Computes: opinion change, agreement scores, influence scores, "
        "and LLM sentiment scores. "
        "The discussion must be complete (POST /discussions must have returned 201). "
        "**Sentiment scoring calls the LLM once per message.**"
    ),
)
def get_analytics(discussion_id: str) -> AnalyticsResponse:
    """Compute and return analytics for a completed discussion."""
    logger.info("analytics_requested  id=%s", discussion_id)

    result = week4_client.get_analytics(discussion_id)

    if not result.success:
        # Distinguish "not found" from a genuine engine failure
        if result.error and "not found" in result.error.lower():
            logger.error("analytics_not_found  id=%s", discussion_id)
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "analytics_export_not_found",
                    "message": result.error,
                },
            )

        logger.error("analytics_failed  id=%s  error=%s", discussion_id, result.error)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "analytics_engine_failed",
                "message": (
                    "The Week 4 analytics engine returned an error. "
                    f"Detail: {result.error}"
                ),
            },
        )

    logger.info("analytics_completed  id=%s", discussion_id)

    return AnalyticsResponse(
        discussion_id=result.discussion_id,
        opinion_change=result.opinion_change,
        agreement=result.agreement,
        influence=result.influence,
        sentiment=result.sentiment,
        stances=getattr(result, "stances", {}),
        interaction_graph=getattr(result, "interaction_graph", {}),
    )
