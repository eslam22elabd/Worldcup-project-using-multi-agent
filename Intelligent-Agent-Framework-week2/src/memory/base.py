from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MemoryStore(ABC):
    """Interface for persistent, per-agent conversation memory."""

    @abstractmethod
    def add(self, session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_recent(self, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def clear(self, session_id: str) -> None:
        raise NotImplementedError
