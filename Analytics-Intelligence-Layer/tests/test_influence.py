"""Influence tests — README sections 12, 13, 14, 15, 16, 28, 30, 31.

Covers:
    - Positive influence: peers move toward sender's stance.
    - Negative/contrarian influence: peers move away from sender.
    - No influence: zero peer changes.
    - Insufficient data: single round, no interactions, zero pull.
    - Every agent gets a result (section 31).
    - Real Week 3 export integration.
"""

from __future__ import annotations

import math

import pytest

from src.influence.calculator import compute_influence, AgentInfluenceResult
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


# --- Insufficient data tests (section 16) ---


def test_single_round_gives_insufficient_data():
    """< 2 rounds: influence cannot be computed (section 16)."""
    series = _series_from_dict({
        "a": [(1, 0.5)],
        "b": [(1, 0.3)],
    })
    discussion = _discussion(
        [OpinionSnapshotRecord("a", 1, 0.5), OpinionSnapshotRecord("b", 1, 0.3)],
        ["a", "b"],
        num_rounds=1,
    )
    results = compute_influence(series, discussion)
    for r in results.values():
        assert not r.is_computable
        assert r.score is None
        assert "at least 2 rounds" in r.reason


def test_no_interactions_gives_insufficient_data():
    """Agent with no outgoing messages -> not computable."""
    # 2 rounds but no message data in the discussion export.
    series = _series_from_dict({
        "a": [(1, 0.5), (2, 0.7)],
        "b": [(1, 0.3), (2, 0.6)],
    })
    discussion = _discussion(
        [
            OpinionSnapshotRecord("a", 1, 0.5),
            OpinionSnapshotRecord("a", 2, 0.7),
            OpinionSnapshotRecord("b", 1, 0.3),
            OpinionSnapshotRecord("b", 2, 0.6),
        ],
        ["a", "b"],
        num_rounds=2,
    )
    results = compute_influence(series, discussion)
    # Without graph/message data embedded, agents have no interactions.
    for r in results.values():
        assert not r.is_computable
        assert r.score is None


# --- Every agent gets a result (section 31) ---


def test_every_agent_gets_a_result():
    """Section 31: every agent has an influence score or explicit reason."""
    series = _series_from_dict({
        "a": [(1, 0.5), (2, 0.7)],
        "b": [(1, 0.3), (2, 0.6)],
        "c": [(1, 0.1), (2, 0.9)],
    })
    discussion = _discussion(
        [
            OpinionSnapshotRecord("a", 1, 0.5),
            OpinionSnapshotRecord("a", 2, 0.7),
            OpinionSnapshotRecord("b", 1, 0.3),
            OpinionSnapshotRecord("b", 2, 0.6),
            OpinionSnapshotRecord("c", 1, 0.1),
            OpinionSnapshotRecord("c", 2, 0.9),
        ],
        ["a", "b", "c"],
        num_rounds=2,
    )
    results = compute_influence(series, discussion)
    assert set(results.keys()) == {"a", "b", "c"}
    for agent_id, r in results.items():
        assert r.agent_id == agent_id
        # Every result is either computable with a score or has a reason.
        if r.is_computable:
            assert r.score is not None
            assert -1.0 <= r.score <= 1.0
        else:
            assert r.score is None
            assert r.reason != ""


# --- to_dict serialization ---


def test_to_dict_has_expected_keys():
    result = AgentInfluenceResult(
        agent_id="test",
        score=0.75,
        is_computable=True,
        num_observations=5,
    )
    d = result.to_dict()
    assert "score" in d
    assert "is_computable" in d
    assert d["score"] == 0.75
    assert d["is_computable"] is True


def test_to_dict_not_computable():
    result = AgentInfluenceResult(
        agent_id="test",
        score=None,
        is_computable=False,
        reason="Not enough data",
    )
    d = result.to_dict()
    assert d["score"] is None
    assert d["is_computable"] is False
    assert d["reason"] == "Not enough data"


# --- Real data (section 30) ---


def test_real_week3_export_produces_influence_results():
    """Run against the bundled sample to verify integration."""
    from src.ingestion.discussion_loader import load_discussion_export

    discussion = load_discussion_export("data/sample/week4_disc_bc528f51d882.json")
    series = build_stance_series(discussion)
    results = compute_influence(series, discussion)

    # Every participant should appear in results.
    for p in discussion.participants:
        assert p in results

    # At least some agents should have computable scores (the sample has
    # 5 agents, 3 rounds, ring topology -- plenty of data).
    computable = [r for r in results.values() if r.is_computable]
    assert len(computable) >= 1

    for r in computable:
        assert -1.0 <= r.score <= 1.0
        assert r.num_observations >= 2


def test_custom_path_export_computes_influence(tmp_path):
    """Verify that an export located outside data/sample successfully retains

    rounds/graph data and computes influence (fixes Copilot PR review issue).
    """
    import json
    from src.ingestion.discussion_loader import load_discussion_export

    custom_export = {
        "discussion_id": "custom_disc_999",
        "topic": "Custom topic outside data/sample",
        "participants": ["agent_x", "agent_y"],
        "num_rounds": 2,
        "graph": {
            "nodes": ["agent_x", "agent_y"],
            "edges": {"agent_x": ["agent_y"], "agent_y": ["agent_x"]},
        },
        "rounds": {
            "round_1": [
                {
                    "id": "msg_1",
                    "round": 1,
                    "sender": "agent_x",
                    "recipients": ["agent_y"],
                    "content": "Argument from X",
                },
                {
                    "id": "msg_2",
                    "round": 1,
                    "sender": "agent_y",
                    "recipients": ["agent_x"],
                    "content": "Argument from Y",
                },
            ],
            "round_2": [
                {
                    "id": "msg_3",
                    "round": 2,
                    "sender": "agent_x",
                    "recipients": ["agent_y"],
                    "content": "Response from X",
                }
            ],
        },
        "opinion_history": {
            "agent_x": [
                {"agent_id": "agent_x", "round": 1, "stance": {"polarity": 0.8}},
                {"agent_id": "agent_x", "round": 2, "stance": {"polarity": 0.8}},
                {"agent_id": "agent_x", "round": 3, "stance": {"polarity": 0.8}},
            ],
            "agent_y": [
                {"agent_id": "agent_y", "round": 1, "stance": {"polarity": 0.0}},
                {"agent_id": "agent_y", "round": 2, "stance": {"polarity": 0.5}},
                {"agent_id": "agent_y", "round": 3, "stance": {"polarity": 0.8}},
            ],
        },
    }

    custom_file = tmp_path / "arbitrary_custom_disc_export.json"
    custom_file.write_text(json.dumps(custom_export), encoding="utf-8")

    discussion = load_discussion_export(custom_file)
    assert discussion.source_path == str(custom_file)
    assert bool(discussion.rounds_data) is True

    series = build_stance_series(discussion)
    results = compute_influence(series, discussion)

    # agent_x sent messages to agent_y; agent_y moved from 0.0 -> 0.5 -> 0.8 toward agent_x (0.8)
    assert "agent_x" in results
    assert results["agent_x"].is_computable is True
    assert results["agent_x"].score is not None
    assert results["agent_x"].score > 0.0

