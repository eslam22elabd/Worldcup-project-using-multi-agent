from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Persona:
    """Configuration that defines an agent's identity and working style."""

    id: str
    name: str
    role: str
    background: str
    stance: str
    communication_style: str
    expertise: list[str]
    priorities: list[str]
    required_tool: str
    input_mode: str

    def as_prompt_text(self) -> str:
        expertise = ", ".join(self.expertise)
        priorities = "; ".join(self.priorities)
        return (
            f"Name: {self.name}\n"
            f"Role: {self.role}\n"
            f"Background: {self.background}\n"
            f"Stance: {self.stance}\n"
            f"Communication style: {self.communication_style}\n"
            f"Expertise: {expertise}\n"
            f"Priorities: {priorities}"
        )


def load_persona(path: str | Path) -> Persona:
    """Load one reusable agent persona from a YAML file."""
    with Path(path).open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    required_fields = {
        "id", "name", "role", "background", "stance", "communication_style",
        "expertise", "priorities", "required_tool", "input_mode",
    }
    missing = required_fields - set(data or {})
    if missing:
        raise ValueError(f"Persona config is missing required fields: {sorted(missing)}")

    return Persona(**data)
