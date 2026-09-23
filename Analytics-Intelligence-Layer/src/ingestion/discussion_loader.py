"""Discussion history loader + validator.

Implements README sections:
    4.  Input: Week 3 Discussion History -> consume Week 3's existing
        export rather than recreating the discussion process.
    27. Data Validation -> validate before computing any metric, and fail
        clearly rather than silently producing incorrect results.

Design decision: two severities.
    - FATAL issues (raise DiscussionValidationError immediately): the file
      cannot be parsed as JSON, or the discussion is unusable for ANY
      analytics (no participants and no opinion history at all -- an
      empty discussion has nothing to analyze).
    - WARNING issues (collected in ValidationReport.warnings, discussion
      still loads): a single malformed snapshot, an agent with no
      opinion data, a duplicate snapshot for the same (agent, round), an
      out-of-range stance value. These affect what that specific agent's
      series looks like, not whether the whole file can be processed --
      per section 27, we do not build "an enormous validation framework",
      we just refuse to silently paper over problems.

This module deliberately only validates what sections 6-8 (Opinion
Change) actually need: participants + opinion_history. It does not
validate message/graph structure needed by the other three analytics
categories (Agreement, Influence, Sentiment), since those are out of
scope for this pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class DiscussionValidationError(ValueError):
    """Raised when a discussion export is unusable for opinion-change analytics."""


@dataclass
class ValidationReport:
    """Non-fatal issues found while loading a discussion, plus context.

    Kept even after a successful load so the caller (and any report/log)
    can see exactly what was skipped or adjusted and why -- satisfying
    section 28's "document what happens when a metric cannot be computed"
    at the level of individual data points.
    """

    warnings: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


@dataclass
class OpinionSnapshotRecord:
    """One validated (agent_id, round, stance) data point.

    Only the fields opinion-change analytics actually need are kept here
    -- this is not a full re-model of Week 3's richer OpinionSnapshot.
    """

    agent_id: str
    round_number: int
    stance: float


@dataclass
class LoadedDiscussion:
    """The validated subset of a Week 3 export needed for opinion-change analytics."""

    discussion_id: str
    topic: str
    participants: list[str]
    num_rounds: int
    snapshots: list[OpinionSnapshotRecord]
    report: ValidationReport
    rounds_data: dict[str, Any] = field(default_factory=dict)
    graph_data: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""

    @property
    def _source_path(self) -> str:
        """Alias for backward-compatibility with callers expecting _source_path."""
        return self.source_path


def load_discussion_export(path: str | Path) -> LoadedDiscussion:
    """Load and validate a Week 3 `week4_*.json` export.

    Raises:
        DiscussionValidationError: if the file is missing, is not valid
            JSON, or the discussion has no usable opinion data at all.

    Returns:
        A LoadedDiscussion with every fatal problem already ruled out,
        and a ValidationReport describing any data points that had to be
        skipped or adjusted along the way.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise DiscussionValidationError(f"Discussion export not found: {file_path}")

    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DiscussionValidationError(f"Discussion export is not valid JSON: {file_path} ({exc})") from exc

    return _validate_and_extract(raw, source=str(file_path))


def _validate_and_extract(raw: dict[str, Any], source: str) -> LoadedDiscussion:
    if not isinstance(raw, dict):
        raise DiscussionValidationError(f"Discussion export must be a JSON object ({source}).")

    discussion_id = raw.get("discussion_id", "")
    topic = raw.get("topic", "")
    num_rounds = raw.get("num_rounds", 0)
    participants = list(raw.get("participants", []))
    opinion_history = raw.get("opinion_history", {})

    report = ValidationReport()

    # --- Fatal: nothing to analyze at all ---------------------------------
    if not participants and not opinion_history:
        raise DiscussionValidationError(
            f"Empty discussion ({source}): no participants and no opinion_history. "
            "Nothing to analyze."
        )
    if not isinstance(opinion_history, dict):
        raise DiscussionValidationError(
            f"Malformed discussion ({source}): 'opinion_history' must be an object "
            "keyed by agent_id."
        )

    # --- Warning: agent listed as a participant but has no opinion data ---
    for agent_id in participants:
        if agent_id not in opinion_history or not opinion_history.get(agent_id):
            report.add(
                f"Agent '{agent_id}' is a participant but has no opinion snapshots -- "
                "its stance series will be empty."
            )

    # --- Warning: opinion data exists for an agent never listed as a participant ---
    for agent_id in opinion_history:
        if agent_id not in participants:
            report.add(
                f"Agent '{agent_id}' has opinion snapshots but is not listed in "
                "'participants' -- including it anyway."
            )

    snapshots: list[OpinionSnapshotRecord] = []
    seen_agent_rounds: set[tuple[str, int]] = set()

    for agent_id, records in opinion_history.items():
        if not isinstance(records, list):
            report.add(f"Agent '{agent_id}': opinion_history entry is not a list -- skipping entirely.")
            continue

        for i, record in enumerate(records):
            if not isinstance(record, dict):
                report.add(f"Agent '{agent_id}', snapshot #{i}: not an object -- skipping.")
                continue

            round_number = record.get("round", record.get("round_number"))
            if round_number is None:
                report.add(f"Agent '{agent_id}', snapshot #{i}: missing round number -- skipping.")
                continue
            try:
                round_number = int(round_number)
            except (TypeError, ValueError):
                report.add(
                    f"Agent '{agent_id}', snapshot #{i}: round number "
                    f"{round_number!r} is not an integer -- skipping."
                )
                continue

            stance_raw = record.get("stance")
            if not isinstance(stance_raw, dict) or "polarity" not in stance_raw:
                report.add(
                    f"Agent '{agent_id}', round {round_number}: missing/malformed stance "
                    "-- skipping this round (insufficient data)."
                )
                continue

            try:
                stance_value = float(stance_raw["polarity"])
            except (TypeError, ValueError):
                report.add(
                    f"Agent '{agent_id}', round {round_number}: stance polarity "
                    f"{stance_raw.get('polarity')!r} is not numeric -- skipping this round."
                )
                continue

            if not (-1.0 <= stance_value <= 1.0):
                clamped = max(-1.0, min(1.0, stance_value))
                report.add(
                    f"Agent '{agent_id}', round {round_number}: stance polarity "
                    f"{stance_value} is outside [-1, 1] -- clamped to {clamped}."
                )
                stance_value = clamped

            key = (agent_id, round_number)
            if key in seen_agent_rounds:
                report.add(
                    f"Agent '{agent_id}', round {round_number}: duplicate snapshot -- "
                    "keeping the first occurrence."
                )
                continue
            seen_agent_rounds.add(key)

            snapshots.append(
                OpinionSnapshotRecord(agent_id=agent_id, round_number=round_number, stance=stance_value)
            )

    if not snapshots:
        raise DiscussionValidationError(
            f"Discussion ({source}) has no usable (agent, round, stance) data points "
            "after validation -- cannot compute opinion change."
        )

    rounds_data = raw.get("rounds") if isinstance(raw.get("rounds"), dict) else {}
    graph_data = raw.get("graph") if isinstance(raw.get("graph"), dict) else {}

    return LoadedDiscussion(
        discussion_id=discussion_id,
        topic=topic,
        participants=participants or sorted({s.agent_id for s in snapshots}),
        num_rounds=num_rounds,
        snapshots=snapshots,
        report=report,
        rounds_data=rounds_data,
        graph_data=graph_data,
        source_path=source,
    )

