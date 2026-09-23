from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent
from src.memory.base import MemoryStore
from src.models.persona import load_persona


def create_agent(persona_path: str | Path, memory: MemoryStore, tools: Any, llm: Any) -> BaseAgent:
    """Create any agent from a persona configuration without changing agent code."""
    persona = load_persona(persona_path)
    return BaseAgent(persona=persona, memory=memory, tools=tools, llm=llm)
