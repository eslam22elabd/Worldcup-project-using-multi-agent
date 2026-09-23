"""Opinion change tests — README sections 6, 8, 28.

Covers: stance series construction, round-to-round change computation,
and explicit handling of agents with 0 or 1 usable data points.
"""

from __future__ import annotations

from src.ingestion.discussion_loader import LoadedDiscussion, OpinionSnapshotRecord, ValidationReport
from src.opinion_change.change_calculator import compute_opinion_change
from src.opinion_change.stance_series import build_stance_series


def _discussion(snapshots: list[OpinionSnapshotRecord], participants: list[str]) -> LoadedDiscussion:
    return LoadedDiscussion(
        discussion_id="disc_test",
        topic="test",
        participants=participants,
        num_rounds=3,
        snapshots=snapshots,
        report=ValidationReport(),
    )


def test_stance_series_sorted_by_round_regardless_of_input_order():
    snapshots = [
        OpinionSnapshotRecord("agent_a", round_number=3, stance=0.9),
        OpinionSnapshotRecord("agent_a", round_number=1, stance=0.1),
        OpinionSnapshotRecord("agent_a", round_number=2, stance=0.5),
    ]
    series = build_stance_series(_discussion(snapshots, ["agent_a"]))
    rounds = [p.round_number for p in series["agent_a"].points]
    assert rounds == [1, 2, 3]


def test_every_participant_gets_an_entry_even_with_zero_data():
    series = build_stance_series(_discussion([], ["agent_a", "agent_b"]))
    assert set(series.keys()) == {"agent_a", "agent_b"}
    assert series["agent_a"].has_data is False
    assert series["agent_a"].points == []


def test_opinion_change_computed_between_consecutive_available_rounds():
    snapshots = [
        OpinionSnapshotRecord("agent_a", round_number=1, stance=0.2),
        OpinionSnapshotRecord("agent_a", round_number=2, stance=0.5),
        OpinionSnapshotRecord("agent_a", round_number=3, stance=0.1),
    ]
    series = build_stance_series(_discussion(snapshots, ["agent_a"]))
    changes = compute_opinion_change(series)

    result = changes["agent_a"]
    assert result.is_computable
    assert [(c.from_round, c.to_round, c.change) for c in result.changes] == [
        (1, 2, 0.3),
        (2, 3, -0.4),
    ]


def test_opinion_change_spans_gap_when_a_round_is_missing():
    # Round 2 is missing entirely for this agent.
    snapshots = [
        OpinionSnapshotRecord("agent_a", round_number=1, stance=0.2),
        OpinionSnapshotRecord("agent_a", round_number=3, stance=0.8),
    ]
    series = build_stance_series(_discussion(snapshots, ["agent_a"]))
    changes = compute_opinion_change(series)

    result = changes["agent_a"]
    assert result.is_computable
    assert len(result.changes) == 1
    assert result.changes[0].from_round == 1
    assert result.changes[0].to_round == 3
    assert result.changes[0].change == 0.6


def test_single_snapshot_is_explicitly_not_computable():
    snapshots = [OpinionSnapshotRecord("agent_a", round_number=1, stance=0.2)]
    series = build_stance_series(_discussion(snapshots, ["agent_a"]))
    changes = compute_opinion_change(series)

    result = changes["agent_a"]
    assert not result.is_computable
    assert result.changes == []
    assert "at least two" in result.reason


def test_zero_snapshots_is_explicitly_not_computable():
    series = build_stance_series(_discussion([], ["agent_a"]))
    changes = compute_opinion_change(series)

    result = changes["agent_a"]
    assert not result.is_computable
    assert result.changes == []
    assert "No stance snapshots" in result.reason


def test_change_values_are_rounded_but_precise():
    snapshots = [
        OpinionSnapshotRecord("agent_a", round_number=1, stance=0.1),
        OpinionSnapshotRecord("agent_a", round_number=2, stance=0.30000001),
    ]
    series = build_stance_series(_discussion(snapshots, ["agent_a"]))
    changes = compute_opinion_change(series)
    assert changes["agent_a"].changes[0].change == 0.2
