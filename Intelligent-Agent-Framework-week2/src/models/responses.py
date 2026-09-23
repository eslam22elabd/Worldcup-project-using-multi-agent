from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Standard result expected from every registered tool."""

    success: bool
    tool_name: str
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Stable handoff object for Week 3's future discussion engine."""

    agent_id: str
    persona_name: str
    topic: str
    opinion: str
    evidence: Any = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    memory_used: bool = False
    session_id: str = ""
