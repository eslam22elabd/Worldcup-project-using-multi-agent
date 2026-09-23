"""Unified analytics entry point.

Implements Week 4 sections 17-19 and connects the four metric categories
without moving their calculations into one large module.

Opinion change, agreement and influence stay in the calculators already
provided by the other parts of the team.  Sentiment is calculated by this
week's sentiment module.  The engine only prepares the shared stance series,
calls each calculator, and returns one structured result for downstream work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.agreement.calculator import compute_agreement
from src.influence.calculator import compute_influence
from src.ingestion.discussion_loader import LoadedDiscussion, load_discussion_export
from src.opinion_change.change_calculator import compute_opinion_change
from src.opinion_change.stance_series import build_stance_series
from src.sentiment.calculator import MessageSentimentResult, compute_sentiment


@dataclass
class AnalyticsResult:
    """Results from all four Week 4 analytics categories."""

    discussion_id: str
    opinion_change: dict[str, Any]
    agreement: list[dict[str, Any]]
    influence: dict[str, Any]
    sentiment: list[MessageSentimentResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "discussion_id": self.discussion_id,
            "opinion_change": {
                agent_id: {
                    "changes": [
                        {
                            "from_round": change.from_round,
                            "to_round": change.to_round,
                            "change": change.change,
                        }
                        for change in result.changes
                    ],
                    "is_computable": result.is_computable,
                    "reason": result.reason,
                }
                for agent_id, result in self.opinion_change.items()
            },
            "agreement": [item.to_dict() for item in self.agreement],
            "influence": {
                agent_id: result.to_dict()
                for agent_id, result in self.influence.items()
            },
            "sentiment": [item.to_dict() for item in self.sentiment],
        }


def run_analytics(discussion: LoadedDiscussion | str | Path) -> AnalyticsResult:
    """Run all four analytics categories for one Week 3 discussion.

    ``discussion`` may be an already-loaded ``LoadedDiscussion`` or the path
    to a Week 3 ``week4_*.json`` export.  No discussion process is recreated.
    """
    if isinstance(discussion, (str, Path)):
        discussion = load_discussion_export(discussion)

    series = build_stance_series(discussion)
    opinion_change = compute_opinion_change(series)
    agreement = compute_agreement(series, num_rounds=discussion.num_rounds)
    influence = compute_influence(series, discussion)
    sentiment = compute_sentiment(discussion)

    return AnalyticsResult(
        discussion_id=discussion.discussion_id,
        opinion_change=opinion_change,
        agreement=agreement,
        influence=influence,
        sentiment=sentiment,
    )
