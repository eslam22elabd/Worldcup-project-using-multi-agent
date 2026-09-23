"""Tests for report generation and visualizations — Section 30.

Covers:
    - Report is non-empty Markdown.
    - Report contains all four required section headers.
    - Opinion trajectory PNG is saved at the expected path.
    - Interaction graph PNG is saved at the expected path.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.ingestion.discussion_loader import LoadedDiscussion, ValidationReport, OpinionSnapshotRecord
from src.opinion_change.stance_series import build_stance_series, AgentStanceSeries, StancePoint
from src.agreement.calculator import RoundAgreementResult
from src.influence.calculator import AgentInfluenceResult
from src.sentiment.calculator import MessageSentimentResult
from src.analytics.engine import AnalyticsResult
from src.opinion_change.change_calculator import AgentChangeResult, OpinionChangePoint


# ── Fixtures ────────────────────────────────────────────────────────────────

def _make_discussion() -> LoadedDiscussion:
    return LoadedDiscussion(
        discussion_id="disc_test",
        topic="Test Topic",
        participants=["agent_a", "agent_b"],
        num_rounds=2,
        snapshots=[
            OpinionSnapshotRecord(agent_id="agent_a", round_number=1, stance=0.5),
            OpinionSnapshotRecord(agent_id="agent_a", round_number=2, stance=0.8),
            OpinionSnapshotRecord(agent_id="agent_b", round_number=1, stance=-0.3),
            OpinionSnapshotRecord(agent_id="agent_b", round_number=2, stance=-0.1),
        ],
        report=ValidationReport(),
        rounds_data={
            "round_1": [
                {"id": "msg_1", "round": 1, "sender": "agent_a",
                 "recipients": ["agent_b"], "content": "Spain played well."},
            ],
            "round_2": [
                {"id": "msg_2", "round": 2, "sender": "agent_b",
                 "recipients": ["agent_a"], "content": "Argentina struggled."},
            ],
        },
    )


def _make_analytics(discussion: LoadedDiscussion) -> AnalyticsResult:
    opinion_change = {
        "agent_a": AgentChangeResult(
            agent_id="agent_a",
            changes=[OpinionChangePoint(agent_id="agent_a", from_round=1, to_round=2, change=0.3)],
        ),
        "agent_b": AgentChangeResult(
            agent_id="agent_b",
            changes=[OpinionChangePoint(agent_id="agent_b", from_round=1, to_round=2, change=0.2)],
        ),
    }
    agreement = [
        RoundAgreementResult(round_number=1, score=0.6, num_agents=2, is_computable=True),
        RoundAgreementResult(round_number=2, score=0.7, num_agents=2, is_computable=True),
    ]
    influence = {
        "agent_a": AgentInfluenceResult(agent_id="agent_a", score=0.5, is_computable=True, num_observations=3),
        "agent_b": AgentInfluenceResult(agent_id="agent_b", score=None, is_computable=False, reason="No data"),
    }
    sentiment = [
        MessageSentimentResult(message_id="msg_1", round_number=1, sender="agent_a", score=0.8, is_computable=True),
        MessageSentimentResult(message_id="msg_2", round_number=2, sender="agent_b", score=-0.4, is_computable=True),
    ]
    return AnalyticsResult(
        discussion_id=discussion.discussion_id,
        opinion_change=opinion_change,
        agreement=agreement,
        influence=influence,
        sentiment=sentiment,
    )


# ── Report tests (Section 30) ────────────────────────────────────────────────

def test_report_is_non_empty():
    from src.reporting.report_generator import generate_report
    discussion = _make_discussion()
    analytics = _make_analytics(discussion)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.md"
        result = generate_report(analytics, discussion, output_path=out)
    assert result.strip(), "Report must not be empty (Section 21)"


def test_report_contains_all_section_headers():
    from src.reporting.report_generator import generate_report
    discussion = _make_discussion()
    analytics = _make_analytics(discussion)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.md"
        result = generate_report(analytics, discussion, output_path=out)
    assert "## Opinion Change" in result
    assert "## Agreement" in result
    assert "## Influence" in result
    assert "## Sentiment" in result


def test_report_is_saved_to_disk():
    from src.reporting.report_generator import generate_report
    discussion = _make_discussion()
    analytics = _make_analytics(discussion)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.md"
        generate_report(analytics, discussion, output_path=out)
        assert out.exists()
        assert out.stat().st_size > 0


# ── Visualization tests (Section 30) ─────────────────────────────────────────

def test_opinion_trajectory_png_created():
    from src.reporting.visualizations import generate_opinion_trajectory
    discussion = _make_discussion()
    series = build_stance_series(discussion)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "trajectory.png"
        result_path = generate_opinion_trajectory(series, "disc_test", output_path=out)
        assert result_path == out
        assert out.exists()
        assert out.stat().st_size > 0


def test_interaction_graph_png_created():
    from src.reporting.visualizations import generate_interaction_graph
    discussion = _make_discussion()
    analytics = _make_analytics(discussion)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.png"
        result_path = generate_interaction_graph(discussion, analytics.influence, output_path=out)
        assert result_path == out
        assert out.exists()
        assert out.stat().st_size > 0
