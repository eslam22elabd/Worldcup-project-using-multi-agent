"""Unified analytics engine tests — Week 4 sections 17-19 and 30-31."""

from __future__ import annotations

from src.analytics.engine import run_analytics
from src.ingestion.discussion_loader import LoadedDiscussion, OpinionSnapshotRecord, ValidationReport


def _discussion() -> LoadedDiscussion:
    return LoadedDiscussion(
        discussion_id="disc_test",
        topic="test",
        participants=["agent_a", "agent_b"],
        num_rounds=2,
        snapshots=[
            OpinionSnapshotRecord("agent_a", 1, 0.2),
            OpinionSnapshotRecord("agent_a", 2, 0.4),
            OpinionSnapshotRecord("agent_b", 1, -0.2),
            OpinionSnapshotRecord("agent_b", 2, 0.0),
        ],
        report=ValidationReport(),
        rounds_data={
            "round_1": [{
                "id": "msg_1", "round": 1, "sender": "agent_a",
                "recipients": ["agent_b"], "content": "A strong and good point."
            }],
            "round_2": [{
                "id": "msg_2", "round": 2, "sender": "agent_b",
                "recipients": ["agent_a"], "content": "A difficult problem was discussed."
            }],
        },
        graph_data={"nodes": ["agent_a", "agent_b"], "edges": {"agent_a": ["agent_b"], "agent_b": ["agent_a"]}},
    )


def test_unified_engine_returns_all_four_metric_categories():
    result = run_analytics(_discussion()).to_dict()

    assert set(result) == {"discussion_id", "opinion_change", "agreement", "influence", "sentiment"}
    assert result["opinion_change"]
    assert len(result["agreement"]) == 2
    assert set(result["influence"]) == {"agent_a", "agent_b"}
    assert len(result["sentiment"]) == 2


def test_unified_engine_keeps_message_ids_in_sentiment_results():
    result = run_analytics(_discussion())
    assert [item.message_id for item in result.sentiment] == ["msg_1", "msg_2"]
