"""Discussion message representation.

A minimal, serializable record of one agent turn within one round.
Kept intentionally small in this scope (sections 6,7,8,9,10,21 only) —
richer fields (retrieval events, opinion snapshots, persistence ids) are
left for the later sections (14-19, 23) that are out of scope for this
pass.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _generate_message_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


def _current_utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Message:
    """One agent's contribution during one discussion round.

    Attributes:
        round_number: 1-indexed round this message belongs to.
        sender_id: The agent id that produced this message.
        recipient_ids: The agent ids that will receive this message
            (determined by the agent graph's outgoing edges for sender_id).
        content: The message text.
        metadata: Free-form extra data (e.g. tool evidence or custom tags).
        message_id: Unique identifier for the message.
        timestamp: ISO-8601 UTC timestamp of creation.
    """

    round_number: int
    sender_id: str
    recipient_ids: list[str]
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=_generate_message_id)
    timestamp: str = field(default_factory=_current_utc_timestamp)

    def as_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of this message."""
        return {
            "id": self.message_id,
            "round": self.round_number,
            "sender": self.sender_id,
            "recipients": list(self.recipient_ids),
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Alias for as_dict() to maintain convention with state serialization."""
        return self.as_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """Construct a Message instance from a dictionary."""
        return cls(
            round_number=data.get("round", data.get("round_number", 1)),
            sender_id=data.get("sender", data.get("sender_id", "")),
            recipient_ids=list(data.get("recipients", data.get("recipient_ids", []))),
            content=data.get("content", ""),
            metadata=dict(data.get("metadata", {})),
            message_id=data.get("id", data.get("message_id", _generate_message_id())),
            timestamp=data.get("timestamp", _current_utc_timestamp()),
        )
