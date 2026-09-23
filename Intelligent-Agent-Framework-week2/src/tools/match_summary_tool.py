"""Tool: get_match_summary

Retrieves structured match statistics for a given game_id from the local
JSON data file (data/matchs summary.json).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.responses import ToolResult

_DEFAULT_DATA_PATH = Path(__file__).parents[2] / "data" / "matchs summary.json"


def get_match_summary(game_id: int, data_path: Path = _DEFAULT_DATA_PATH) -> ToolResult:
    """Return the full structured match summary for the given game_id.

    Args:
        game_id: The unique integer identifier for the match.
        data_path: Path to the JSON file containing match summaries.

    Returns:
        ToolResult with match data dict on success, error message on failure.
    """
    try:
        with data_path.open("r", encoding="utf-8") as f:
            raw: dict[str, Any] = json.load(f)
    except FileNotFoundError:
        return ToolResult(
            success=False,
            tool_name="get_match_summary",
            error=f"Data file not found: {data_path}",
        )
    except json.JSONDecodeError as exc:
        return ToolResult(
            success=False,
            tool_name="get_match_summary",
            error=f"Failed to parse match summary JSON: {exc}",
        )

    # The JSON has the shape {"Sheet1": [...]} based on the actual data file.
    records: list[dict[str, Any]] = raw.get("Sheet1", [])

    for record in records:
        if record.get("Game id") == game_id:
            match_label = record.get("Game / Match", f"game_id={game_id}")
            return ToolResult(
                success=True,
                tool_name="get_match_summary",
                data=record,
                metadata={"game_id": game_id, "match_label": match_label},
            )

    return ToolResult(
        success=False,
        tool_name="get_match_summary",
        error=f"No match summary found for game_id={game_id}.",
    )
