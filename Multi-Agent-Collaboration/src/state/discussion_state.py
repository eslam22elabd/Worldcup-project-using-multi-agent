"""Discussion state engine.

Maintains the centralized, in-memory state of an ongoing or completed
multi-round multi-agent discussion, with clean extension points.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.discussion.message import Message


def _generate_discussion_id() -> str:
    return f"disc_{uuid.uuid4().hex[:12]}"


def _current_utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class DiscussionStatus(str, Enum):
    """Lifecycle state of a discussion."""

    INITIALIZING = "initializing"
    IN_PROGRESS = "in_progress"
    ROUND_COMPLETE = "round_complete"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    FAILED = "failed"


@dataclass
class DiscussionState:
    """Centralized state representation for a multi-agent discussion.

    Attributes:
        topic: The discussion topic / prompt.
        graph_config: Serialized agent graph structure (nodes & edges).
        num_rounds: Configured target number of rounds (minimum 3).
        participants: Ordered list of agent IDs participating.
        discussion_id: Unique identifier for this discussion run.
        current_round: Current 1-indexed round (0 before discussion starts).
        status: Current lifecycle state of the discussion.
        messages: Chronological log of all messages produced and routed.
        opinions: Extension slot for Teammate 3's Opinion Tracking
            {agent_id: [opinion_record, ...]}.
        retrieval_events: Extension slot for Mid-Discussion Retrieval
            [retrieval_record, ...].
        checkpoints: Snapshots of state captured at round boundaries.
        metadata: Extensible runtime metadata (e.g., game_id, model configs).
        started_at: ISO-8601 UTC timestamp of creation.
        completed_at: ISO-8601 UTC timestamp of completion (or None).
        termination_reason: Explanatory string when discussion finishes.
    """

    topic: str
    graph_config: dict[str, Any] = field(default_factory=dict)
    num_rounds: int = 3
    participants: list[str] = field(default_factory=list)
    discussion_id: str = field(default_factory=_generate_discussion_id)
    current_round: int = 0
    status: DiscussionStatus = DiscussionStatus.INITIALIZING
    messages: list[Message] = field(default_factory=list)
    opinions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    retrieval_events: list[dict[str, Any]] = field(default_factory=list)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=_current_utc_timestamp)
    completed_at: str | None = None
    termination_reason: str = ""

    @property
    def graph(self) -> dict[str, Any]:
        """Alias for graph_config to maintain 100% backward compatibility with DiscussionTrace."""
        return self.graph_config

    def __post_init__(self) -> None:
        if self.num_rounds < 3:
            raise ValueError("DiscussionState.num_rounds must be at least 3.")

        # Infer participants from graph_config if not explicitly provided
        if not self.participants and "nodes" in self.graph_config:
            self.participants = list(self.graph_config["nodes"])
            
        # Ensure opinion mapping is initialized for all participants
        for participant in self.participants:
            if participant not in self.opinions:
                self.opinions[participant] = []
    # ------------------------------------------------------------------
    # Lifecycle & Round Progression
    # ------------------------------------------------------------------

    def start_round(self, round_number: int) -> None:
        """Advance the discussion to the specified round."""
        self.current_round = round_number
        self.status = DiscussionStatus.IN_PROGRESS

    def finish_round(self, round_number: int) -> None:
        """Mark the given round as completed and capture a checkpoint."""
        if round_number != self.current_round:
            raise ValueError(
                f"finish_round({round_number}) called but current_round is {self.current_round}"
        )
        self.status = DiscussionStatus.ROUND_COMPLETE
        self.create_checkpoint(label=f"round_{self.current_round}_complete")

    def complete(self, reason: str = "") -> None:
        """Mark the discussion as cleanly completed."""
        self.status = DiscussionStatus.COMPLETED
        self.completed_at = _current_utc_timestamp()
        self.termination_reason = reason or f"Completed {self.current_round}/{self.num_rounds} rounds."
        self.create_checkpoint(label="discussion_completed")

    def terminate(self, reason: str) -> None:
        """Mark the discussion as terminated early or on failure."""
        self.status = DiscussionStatus.TERMINATED
        self.completed_at = _current_utc_timestamp()
        self.termination_reason = reason
        self.create_checkpoint(label="discussion_terminated")

    # ------------------------------------------------------------------
    # Message Management
    # ------------------------------------------------------------------

    def add_message(self, message: Message) -> None:
        """Append a routed message to the discussion history."""
        self.messages.append(message)

    def messages_for(self, agent_id: str) -> list[Message]:
        """Return all messages ever routed to `agent_id`, in chronological order."""
        return [m for m in self.messages if agent_id in m.recipient_ids]

    def get_round_messages(self, round_number: int) -> list[Message]:
        """Return all messages produced in a specific round."""
        return [m for m in self.messages if m.round_number == round_number]

    def record_opinion(
        self,
        agent_id: str,
        round_number: int,
        opinion: str,
        stance: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Records an agent's opinion snapshot for a given round.

        """
        record = {
            "agent_id": agent_id,
            "round": round_number,
            "opinion": opinion,
            "stance": stance,
            "timestamp": _current_utc_timestamp(),
            "metadata": dict(metadata or {}),
        }
        if agent_id not in self.opinions:
            self.opinions[agent_id] = []
        self.opinions[agent_id].append(record)
        return record

    def record_retrieval(
        self,
        agent_id: str,
        round_number: int,
        query: str,
        evidence: Any,
        tool_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Records a knowledge retrieval event occurring during discussion.
        """
        record = {
            "event_id": f"ret_{uuid.uuid4().hex[:8]}",
            "agent_id": agent_id,
            "round": round_number,
            "query": query,
            "evidence": evidence,
            "tool_name": tool_name,
            "timestamp": _current_utc_timestamp(),
            "metadata": dict(metadata or {}),
        }
        self.retrieval_events.append(record)
        return record

    # ------------------------------------------------------------------
    # Checkpointing & Serialization
    # ------------------------------------------------------------------

    def create_checkpoint(self, label: str = "") -> dict[str, Any]:
        """Capture a deep-copy snapshot of the current state at this moment."""
        snapshot = {
            "checkpoint_id": f"chk_{uuid.uuid4().hex[:8]}",
            "label": label or f"round_{self.current_round}",
            "timestamp": _current_utc_timestamp(),
            "current_round": self.current_round,
            "status": self.status.value,
            "message_count": len(self.messages),
        }
        self.checkpoints.append(snapshot)
        return snapshot

    def to_dict(self) -> dict[str, Any]:
        """
        Return a complete, JSON-serializable representation of this state.
        """
        return {
            "discussion_id": self.discussion_id,
            "topic": self.topic,
            "participants": list(self.participants),
            "graph": copy.deepcopy(self.graph_config),
            "num_rounds": self.num_rounds,
            "current_round": self.current_round,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "termination_reason": self.termination_reason,
            "messages": [m.as_dict() for m in self.messages],
            "opinions": copy.deepcopy(self.opinions),
            "retrieval_events": copy.deepcopy(self.retrieval_events),
            "checkpoints": copy.deepcopy(self.checkpoints),
            "metadata": copy.deepcopy(self.metadata),
        }

    def as_dict(self) -> dict[str, Any]:
        """Alias for to_dict() for backward compatibility with DiscussionTrace."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiscussionState:
        """Reconstruct a DiscussionState instance from a serialized dictionary."""
        messages = [
            Message.from_dict(m) if isinstance(m, dict) else m
            for m in data.get("messages", [])
        ]
        status_val = data.get("status", DiscussionStatus.INITIALIZING.value)
        try:
            status = DiscussionStatus(status_val)
        except ValueError:
            status = DiscussionStatus.INITIALIZING

        return cls(
            topic=data.get("topic", ""),
            graph_config=dict(data.get("graph", data.get("graph_config", {}))),
            num_rounds=data.get("num_rounds", 3),
            participants=list(data.get("participants", [])),
            discussion_id=data.get("discussion_id", _generate_discussion_id()),
            current_round=data.get("current_round", 0),
            status=status,
            messages=messages,
            opinions=dict(data.get("opinions", {})),
            retrieval_events=list(data.get("retrieval_events", [])),
            checkpoints=list(data.get("checkpoints", [])),
            metadata=dict(data.get("metadata", {})),
            started_at=data.get("started_at", _current_utc_timestamp()),
            completed_at=data.get("completed_at"),
            termination_reason=data.get("termination_reason", ""),
        )
