"""Tool: get_match_opinions

Retrieves analyst opinions for a given game_id from the local JSON data
file (data/opinion.json).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import re as _re

from src.models.responses import ToolResult

_DEFAULT_DATA_PATH = Path(__file__).parents[2] / "data" / "opinion.json"


def get_match_opinions(game_id: int, data_path: Path = _DEFAULT_DATA_PATH) -> ToolResult:
    """Return the four analyst opinions for the given game_id.

    Args:
        game_id: The unique integer identifier for the match.
        data_path: Path to the JSON file containing opinions.

    Returns:
        ToolResult with opinions dict on success, error message on failure.
    """
    try:
        with data_path.open("r", encoding="utf-8") as f:
            content = f.read().strip()

        # opinion.json is a sequence of concatenated JSON objects (not a proper
        # JSON array). We normalise it by wrapping in [] and inserting commas.
        if content.startswith("{"):
            # Replace every occurrence of "}\n{" (with any whitespace) with "},\n{"
            
            fixed = _re.sub(r"\}\s*\n\s*\{", "},\n{", content)
            records: list[dict[str, Any]] = json.loads(f"[{fixed}]")
        elif content.startswith("["):
            records = json.loads(content)
        else:
            raw = json.loads(content)
            records = raw if isinstance(raw, list) else next(
                (v for v in raw.values() if isinstance(v, list)), []
            )
    except FileNotFoundError:
        return ToolResult(
            success=False,
            tool_name="get_match_opinions",
            error=f"Data file not found: {data_path}",
        )
    except json.JSONDecodeError as exc:
        return ToolResult(
            success=False,
            tool_name="get_match_opinions",
            error=f"Failed to parse opinions JSON: {exc}",
        )

    for record in records:
        if record.get("game_id") == game_id:
            # Collect all opinion fields present in the record
            opinions = {
                key: value
                for key, value in record.items()
                if key.startswith("opinion")
            }
            formatted = "\n\n".join(
                f"[{key.upper()}]\n{value}" for key, value in opinions.items()
            )
            return ToolResult(
                success=True,
                tool_name="get_match_opinions",
                data=formatted,
                metadata={"game_id": game_id, "opinion_count": len(opinions)},
            )

    return ToolResult(
        success=False,
        tool_name="get_match_opinions",
        error=f"No opinions found for game_id={game_id}.",
    )
