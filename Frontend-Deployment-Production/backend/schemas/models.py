"""schemas/models.py — Pydantic request/response models for all endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response for GET /health"""

    status: str = Field("ok", description="Always 'ok' while the process is alive.")

    model_config = {"json_schema_extra": {"example": {"status": "ok"}}}


# ---------------------------------------------------------------------------
# GET /topics
# ---------------------------------------------------------------------------

class TopicsResponse(BaseModel):
    """Response for GET /topics."""

    topics: list[str] = Field(
        ...,
        description="Human-readable topic labels the discussion engine knows about.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "topics": [
                    "Argentina vs Spain — 2026 FIFA World Cup Final",
                    "France vs England — 2026 FIFA World Cup Third Place Play-off",
                ]
            }
        }
    }


# ---------------------------------------------------------------------------
# POST /discussions
# ---------------------------------------------------------------------------

class CreateDiscussionRequest(BaseModel):
    """Request body for POST /discussions."""

    topic: str = Field(
        ...,
        min_length=1,
        description=(
            "Free-text topic or match description (Arabic or English). "
            "The engine auto-detects the matching persona set."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {"topic": "Argentina vs Spain — who deserved to win?"}
        }
    }


class CreateDiscussionResponse(BaseModel):
    """Response for POST /discussions."""

    discussion_id: str = Field(..., description="Unique ID for the new discussion (e.g. 'disc_abc123').")
    status: str = Field(..., description="'completed' once all rounds finish.")
    topic: str = Field(..., description="Canonical topic string the engine used.")
    agents: list[str] = Field(..., description="Persona IDs that participated.")
    num_rounds: int = Field(..., description="Number of rounds that ran.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "discussion_id": "disc_abc123def456",
                "status": "completed",
                "topic": "Argentina vs Spain — 2026 FIFA World Cup Final",
                "agents": ["arg_esp_tactical_analyst", "arg_esp_argentina_fan"],
                "num_rounds": 3,
            }
        }
    }


# ---------------------------------------------------------------------------
# GET /discussions/{discussion_id}
# ---------------------------------------------------------------------------

class AgentMessage(BaseModel):
    """One agent message inside a round."""

    agent: str = Field(..., description="The agent (persona) that sent this message.")
    text: str = Field(..., description="Message content.")
    message_id: str = Field(..., description="Unique message ID.")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp.")


class Round(BaseModel):
    """All messages produced in a single discussion round."""

    round: int = Field(..., description="1-indexed round number.")
    messages: list[AgentMessage]


class DiscussionResponse(BaseModel):
    """Response for GET /discussions/{discussion_id}."""

    discussion_id: str
    topic: str
    status: str
    agents: list[str] = Field(..., description="All participating agent IDs.")
    num_rounds: int
    rounds: list[Round]
    started_at: str
    completed_at: str | None = None
    termination_reason: str = ""

    model_config = {
        "json_schema_extra": {
            "example": {
                "discussion_id": "disc_abc123",
                "topic": "Argentina vs Spain — 2026 FIFA World Cup Final",
                "status": "completed",
                "agents": ["arg_esp_tactical_analyst", "arg_esp_argentina_fan"],
                "num_rounds": 3,
                "rounds": [
                    {
                        "round": 1,
                        "messages": [
                            {
                                "agent": "arg_esp_tactical_analyst",
                                "text": "Argentina dominated possession...",
                                "message_id": "msg_abc",
                                "timestamp": "2026-09-20T06:00:12+00:00",
                            }
                        ],
                    }
                ],
                "started_at": "2026-09-20T06:00:00+00:00",
                "completed_at": "2026-09-20T06:05:00+00:00",
                "termination_reason": "Reached configured num_rounds=3.",
            }
        }
    }


# ---------------------------------------------------------------------------
# GET /discussions/{discussion_id}/analytics
# ---------------------------------------------------------------------------

class AnalyticsResponse(BaseModel):
    """Response for GET /discussions/{discussion_id}/analytics."""

    discussion_id: str
    opinion_change: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-agent opinion change results (Week 4).",
    )
    agreement: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-round agreement scores (Week 4).",
    )
    influence: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-agent influence scores (Week 4).",
    )
    sentiment: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-message LLM sentiment scores (Week 4).",
    )
    stances: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-agent numeric stance series across rounds (Week 4).",
    )
    interaction_graph: dict[str, Any] = Field(
        default_factory=dict,
        description="Interaction network graph representing agent relationships and message flows (Week 4).",
    )


# ---------------------------------------------------------------------------
# Generic error body (used with HTTPException detail)
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    """Shape of the 'detail' field in every HTTPException response."""

    error: str = Field(..., description="Short machine-readable error label.")
    message: str = Field(..., description="Human-readable description.")
