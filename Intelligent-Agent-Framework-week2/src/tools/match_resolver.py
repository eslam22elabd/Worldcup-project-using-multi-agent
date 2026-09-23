"""MatchResolver — converts a natural-language match query into a game_id.

The user can type things like:
  - "Mexico South Africa"
  - "Mexico vs South Africa"
  - "World Cup Mexico"

The resolver searches the match summary JSON and returns the best candidate(s).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_DATA_PATH = Path(__file__).parents[2] / "data" / "matchs summary.json"


@dataclass
class MatchCandidate:
    """A match candidate returned by the resolver."""

    game_id: int
    label: str          # Human-readable "Date Team1 vs Team2"
    home_team: str
    away_team: str
    stage: str
    score: str

    def display(self) -> str:
        return (
            f"  [{self.game_id}]  {self.label}  |  "
            f"{self.home_team} {self.score} {self.away_team}  "
            f"({self.stage})"
        )


class MatchResolver:
    """Resolves a user query to one or more MatchCandidate objects.

    Args:
        data_path: Path to the match summary JSON file.
    """

    def __init__(self, data_path: Path = _DEFAULT_DATA_PATH) -> None:
        self._records: list[dict[str, Any]] = self._load(data_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as f:
            raw: dict[str, Any] = json.load(f)
        return raw.get("Sheet1", [])

    @staticmethod
    def _to_candidate(record: dict[str, Any]) -> MatchCandidate:
        return MatchCandidate(
            game_id=record["Game id"],
            label=record.get("Game / Match", ""),
            home_team=record.get("Home Team", ""),
            away_team=record.get("Away Team", ""),
            stage=record.get("Stage", ""),
            score=record.get("Final Score", ""),
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase and collapse whitespace for fuzzy matching."""
        return re.sub(r"\s+", " ", text.lower().strip())

    def _score_record(self, record: dict[str, Any], tokens: list[str]) -> int:
        """Return how many query tokens appear in the record's searchable text."""
        searchable = self._normalize(
            " ".join([
                str(record.get("Game id", "")),
                record.get("Game / Match", ""),
                record.get("Home Team", ""),
                record.get("Away Team", ""),
                record.get("Stage", ""),
            ])
        )
        return sum(1 for token in tokens if token in searchable)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, query: str) -> list[MatchCandidate]:
        """Resolve a user query to a ranked list of MatchCandidates.

        If the query is a plain integer, look up that exact game_id.
        Otherwise, score each record by how many query tokens it contains
        and return all records that share the maximum score (≥ 1 token match).

        Returns:
            A list of MatchCandidate objects, best match first.
            Empty list if no match is found.
        """
        query_stripped = query.strip()

        # --- Exact numeric game_id lookup ---
        if query_stripped.isdigit():
            gid = int(query_stripped)
            for record in self._records:
                if record.get("Game id") == gid:
                    return [self._to_candidate(record)]
            return []

        # --- Fuzzy token matching ---
        tokens = self._normalize(query_stripped).split()
        # Remove common noise words
        _NOISE = {"vs", "versus", "-", "and", "the", "match", "game", "مباراة", "ضد"}
        tokens = [t for t in tokens if t not in _NOISE]

        if not tokens:
            return []

        scored = [
            (self._score_record(r, tokens), r)
            for r in self._records
        ]
        max_score = max(s for s, _ in scored)

        if max_score == 0:
            return []

        best = [r for s, r in scored if s == max_score]
        return [self._to_candidate(r) for r in best]

    def build_search_query(self, candidate: MatchCandidate) -> str:
        """Build a web search query string for the given match candidate."""
        return (
            f"{candidate.home_team} vs {candidate.away_team} "
            f"{candidate.stage} match analysis highlights"
        )

    def all_matches(self) -> list[MatchCandidate]:
        """Return all available matches (useful for listing)."""
        return [self._to_candidate(r) for r in self._records]
