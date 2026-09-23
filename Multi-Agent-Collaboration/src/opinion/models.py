from __future__ import annotations
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

def _current_utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

class OpinionShiftType(str, Enum):
    STRENGTHENED = "strengthened"
    WEAKENED = "weakened"
    SHIFTED = "shifted"
    UNCHANGED = "unchanged"
    REVERSED = "reversed"


@dataclass
class Stance:
    polarity: float = 0.0

    def __post_init__(self) -> None:
        self.polarity = max(-1.0, min(1.0, float(self.polarity)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "polarity": round(self.polarity, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Stance:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            polarity=float(data.get("polarity", 0.0)),
        )


@dataclass
class OpinionSnapshot:
    agent_id: str
    round_number: int
    opinion_text: str
    stance: Stance = field(default_factory=Stance)
    timestamp: str = field(default_factory=_current_utc_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_initial(self) -> bool:
        return self.round_number == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "round": self.round_number,
            "opinion": self.opinion_text,
            "stance": self.stance.to_dict(),
            "timestamp": self.timestamp,
            "metadata": copy.deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpinionSnapshot:
        stance_raw = data.get("stance")
        stance = Stance.from_dict(stance_raw) if isinstance(stance_raw, dict) else Stance()
        return cls(
            agent_id=data.get("agent_id", ""),
            round_number=data.get("round", data.get("round_number", 0)),
            opinion_text=data.get("opinion", data.get("opinion_text", "")),
            stance=stance,
            timestamp=data.get("timestamp", _current_utc_timestamp()),
            metadata=dict(data.get("metadata", {})),
        )

@dataclass
class OpinionShift:
    agent_id: str
    from_round: int
    to_round: int
    shift_type: OpinionShiftType
    delta_polarity: float
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "from_round": self.from_round,
            "to_round": self.to_round,
            "shift_type": self.shift_type.value,
            "delta_polarity": round(self.delta_polarity, 4),
            "explanation": self.explanation,
        }

