"""Agreement / Disagreement scoring.
------------------------------------------------------------------------
Formula
------------------------------------------------------------------------
For each round r with N agents that have a valid stance value:

    1. Collect all stance values:  S = {s_1, s_2, ..., s_N}
       where each s_i in [-1.0, 1.0].

    2. Calculate every pairwise absolute difference:
           d(i, j) = |s_i - s_j|       for all i < j
       There are P = N*(N-1)/2 such pairs.

    3. Average pairwise difference:
           d_avg = sum(d(i,j)) / P

    4. Normalize by the maximum possible difference (2.0, since
       stances range from -1 to +1):
           d_norm = d_avg / 2.0         in [0.0, 1.0]

    5. Agreement score:
           Agreement(r) = 1.0 - d_norm  in [0.0, 1.0]

Interpretation:
    1.0  = perfect consensus (all stances identical).
    0.0  = maximum polarization (agents at -1.0 and +1.0).
    >0.75 = high agreement.
    <0.50 = strong divergence.

Edge cases:
    - 0 or 1 agents with valid stances in a round: not computable.
      Score is None with a human-readable reason (section 28).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from src.opinion_change.stance_series import AgentStanceSeries


@dataclass
class RoundAgreementResult:
    """Agreement score for one discussion round.

    Attributes:
        round_number: Which round this score belongs to.
        score: The agreement score in [0.0, 1.0], or None if not computable.
        num_agents: How many agents had valid stance data in this round.
        is_computable: Whether a meaningful score could be calculated.
        reason: Why the score is not computable (empty string if it is).
    """

    round_number: int
    score: float | None
    num_agents: int
    is_computable: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the format expected by section 19's unified result.

        Returns {"round": 1, "score": 0.74} when computable,
        or {"round": 1, "score": null} with a reason field when not.
        """
        result: dict[str, Any] = {
            "round": self.round_number,
            "score": round(self.score, 4) if self.score is not None else None,
        }
        if not self.is_computable:
            result["reason"] = self.reason
        return result


def compute_agreement(
    series: dict[str, AgentStanceSeries],
    num_rounds: int | None = None,
) -> list[RoundAgreementResult]:
    """Compute one agreement score per round (sections 9-11).

    Args:
        series: Per-agent stance series (output of build_stance_series).
        num_rounds: Total number of rounds in the discussion.  If None,
            inferred from the maximum round number found in the data.

    Returns:
        A list of RoundAgreementResult, one per round, sorted by round.
        Rounds where fewer than 2 agents have data get score=None with
        a descriptive reason (section 28).
    """
    # Determine the set of rounds to score.
    all_rounds: set[int] = set()
    for agent_series in series.values():
        for p in agent_series.points:
            all_rounds.add(p.round_number)

    if num_rounds is not None:
        all_rounds.update(range(1, num_rounds + 1))

    if not all_rounds:
        return []

    results: list[RoundAgreementResult] = []

    for r in sorted(all_rounds):
        # Gather every agent's stance for this round.
        stances: list[float] = []
        for agent_series in series.values():
            s = agent_series.stance_at(r)
            if s is not None:
                stances.append(s)

        n = len(stances)

        if n < 2:
            results.append(
                RoundAgreementResult(
                    round_number=r,
                    score=None,
                    num_agents=n,
                    is_computable=False,
                    reason=(
                        f"Agreement requires at least 2 agents with stance data "
                        f"in the round; found {n}."
                    ),
                )
            )
            continue

        # Pairwise absolute differences.
        pair_diffs = [abs(a - b) for a, b in combinations(stances, 2)]

        # Average pairwise difference, normalized by max possible diff (2.0).
        avg_diff = sum(pair_diffs) / len(pair_diffs)
        score = round(1.0 - (avg_diff / 2.0), 6)

        results.append(
            RoundAgreementResult(
                round_number=r,
                score=score,
                num_agents=n,
                is_computable=True,
            )
        )

    return results
