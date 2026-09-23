from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base import MemoryStore


class JsonMemoryStore(MemoryStore):
    """Simple persistent memory: one JSON file per agent session."""

    def __init__(self, root_dir: str | Path = "data/memory") -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in session_id)
        return self.root_dir / f"{safe_id}.json"

    def _load(self, session_id: str) -> list[dict[str, Any]]:
        path = self._path(session_id)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        with self._path(session_id).open("w", encoding="utf-8") as file:
            json.dump(messages, file, ensure_ascii=False, indent=2)

    def add(self, session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        if role not in {"user", "assistant", "system", "tool"}:
            raise ValueError("role must be one of: user, assistant, system, tool")

        messages = self._load(session_id)
        messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        })
        self._save(session_id, messages)

    def get_recent(self, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return self._load(session_id)[-limit:]

    def clear(self, session_id: str) -> None:
        path = self._path(session_id)
        if path.exists():
            path.unlink()
