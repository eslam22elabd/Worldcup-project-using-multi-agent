"""Agreement tests — README sections 9, 10, 11, 28, 30, 31.

Covers:
    - Perfect consensus (score = 1.0).
    - Maximum polarization (score = 0.0).
    - Partial agreement with known values.
    - Round with 0 or 1 agent (not computable, section 28).
    - Multiple rounds with mixed computability.
    - Real Week 3 export produces a score for every round.
"""

from __future__ import annotations

import pytest

from src.agreement.calculator import compute_agreement, RoundAgreementResult
from src.ingestion.discussion_loader import LoadedDiscussion, OpinionSnapshotRecord, ValidationReport
from src.opinion_change.stance_series import AgentStanceSeries, StancePoint, build_stance_series


def _discussion(snapshots, participants, num_rounds=3):
    return LoadedDiscussion(
        discussion_id="disc_test",
        topic="test",
        participants=participants,
        num_rounds=num_rounds,
        snapshots=snapshots,
        report=ValidationReport(),
    )


def _series_from_dict(data: dict[str, list[tuple[int, float]]]) -> dict[str, AgentStanceSeries]:
    """Shorthand: {"agent_a": [(1, 0.5), (2, 0.7)]} -> stance series."""
    result = {}
    for agent_id, points in data.items():
        result[agent_id] = AgentStanceSeries(
            agent_id=agent_id,
            points=[StancePoint(round_number=r, stance=s) for r, s in points],
        )
    return result


# --- Core formula tests ---


def test_perfect_consensus_gives_score_1():
    """All agents have the same stance -> agreement = 1.0."""
    series = _series_from_dict({
        "a": [(1, 0.5)],
        "b": [(1, 0.5)],
        "c": [(1, 0.5)],
    })
    results = compute_agreement(series)
    assert len(results) == 1
    assert results[0].score == 1.0
    assert results[0].is_computable


def test_maximum_polarization_gives_score_0():
    """Two agents at opposite extremes (-1 and +1) -> agreement = 0.0."""
    series = _series_from_dict({
        "a": [(1, -1.0)],
        "b": [(1, 1.0)],
    })
    results = compute_agreement(series)
    assert results[0].score == 0.0
    assert results[0].is_computable


def test_known_partial_agreement():
    """Three agents with stances 0.7, 0.65, 0.72 -> high agreement.

    Pairwise diffs: |0.7-0.65|=0.05, |0.7-0.72|=0.02, |0.65-0.72|=0.07
    avg_diff = (0.05 + 0.02 + 0.07) / 3 = 0.046667
    agreement = 1 - 0.046667/2.0 = 0.976667
    """
    series = _series_from_dict({
        "a": [(1, 0.70)],
        "b": [(1, 0.65)],
        "c": [(1, 0.72)],
    })
    results = compute_agreement(series)
    assert results[0].is_computable
    assert abs(results[0].score - 0.976667) < 0.001


def test_high_disagreement_example():
    """Stances 0.9, -0.8, 0.1 -> low agreement.

    Pairwise diffs: |0.9-(-0.8)|=1.7, |0.9-0.1|=0.8, |(-0.8)-0.1|=0.9
    avg_diff = (1.7 + 0.8 + 0.9) / 3 = 1.1333
    agreement = 1 - 1.1333/2.0 = 0.4333
    """
    series = _series_from_dict({
        "a": [(1, 0.9)],
        "b": [(1, -0.8)],
        "c": [(1, 0.1)],
    })
    results = compute_agreement(series)
    assert results[0].is_computable
    assert abs(results[0].score - 0.4333) < 0.001


# --- Edge cases (section 28) ---


def test_single_agent_round_is_not_computable():
    """Only 1 agent in a round -> cannot compute pairwise differences."""
    series = _series_from_dict({"a": [(1, 0.5)]})
    results = compute_agreement(series)
    assert len(results) == 1
    assert not results[0].is_computable
    assert results[0].score is None
    assert "at least 2" in results[0].reason


def test_zero_agents_in_round_is_not_computable():
    """A round number exists (via num_rounds) but no agent has data."""
    series = _series_from_dict({
        "a": [(2, 0.5)],
        "b": [(2, 0.3)],
    })
    # Round 1 has no data; round 2 has data.
    results = compute_agreement(series, num_rounds=2)
    round_1 = [r for r in results if r.round_number == 1][0]
    round_2 = [r for r in results if r.round_number == 2][0]
    assert not round_1.is_computable
    assert round_1.score is None
    assert round_2.is_computable


# --- Multi-round ---


def test_multiple_rounds_each_get_a_score():
    """Section 10: one agreement score per discussion round."""
    series = _series_from_dict({
        "a": [(1, 0.5), (2, 0.8)],
        "b": [(1, 0.5), (2, -0.2)],
    })
    results = compute_agreement(series)
    assert len(results) == 2
    assert results[0].round_number == 1
    assert results[1].round_number == 2
    # Round 1: same stances -> 1.0.
    assert results[0].score == 1.0
    # Round 2: diff = |0.8-(-0.2)| = 1.0, agreement = 1 - 1.0/2.0 = 0.5.
    assert results[1].score == 0.5


# --- to_dict serialization ---


def test_to_dict_matches_section_19_format():
    series = _series_from_dict({
        "a": [(1, 0.3)],
        "b": [(1, 0.7)],
    })
    results = compute_agreement(series)
    d = results[0].to_dict()
    assert "round" in d
    assert "score" in d
    assert d["round"] == 1
    assert isinstance(d["score"], float)


def test_to_dict_includes_reason_when_not_computable():
    series = _series_from_dict({"a": [(1, 0.5)]})
    results = compute_agreement(series)
    d = results[0].to_dict()
    assert d["score"] is None
    assert "reason" in d


# --- Real data (section 30) ---


def test_real_week3_export_produces_agreement_for_every_round():
    """Run against the bundled sample to verify integration."""
    from src.ingestion.discussion_loader import load_discussion_export

    discussion = load_discussion_export("data/sample/week4_disc_bc528f51d882.json")
    series = build_stance_series(discussion)
    results = compute_agreement(series, num_rounds=discussion.num_rounds)

    # Must have at least one result per round.
    assert len(results) >= discussion.num_rounds

    # Every result that IS computable should have a score in [0, 1].
    for r in results:
        if r.is_computable:
            assert 0.0 <= r.score <= 1.0
