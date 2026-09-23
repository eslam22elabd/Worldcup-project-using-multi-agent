"""Opinion change calculation.

Implements README sections:
    8.  Opinion Change -> change = stance(current round) - stance(previous
        round), for every agent, at every round where it's computable.
    28. Handling Missing Data -> "Opinion change requires multiple stance
        snapshots" -- this module makes that requirement explicit and
        machine-checkable rather than assumed.

Design decision: change is computed between an agent's own CONSECUTIVE
AVAILABLE data points, not between round N and round N-1 by number. If
an agent is missing round 2 but has rounds 1 and 3, the change entry
covers from_round=1, to_round=3 -- both endpoints are recorded explicitly
so this is inspectable (the acceptance criterion in section 8 requires a
trajectory that can be inspected), rather than silently interpolating or
skipping the gap without a trace.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.opinion_change.stance_series import AgentStanceSeries


@dataclass
class OpinionChangePoint:
    """The change in stance between two consecutive available rounds for one agent."""

    agent_id: str
    from_round: int
    to_round: int
    change: float


@dataclass
class AgentChangeResult:
    """An agent's full set of computed changes, plus why data is missing if it is.

    `changes` is empty when change cannot be computed at all -- `reason`
    then explains why (per section 28: "document what happens when a
    metric cannot be computed"), instead of returning an empty list with
    no explanation.
    """

    agent_id: str
    changes: list[OpinionChangePoint]
    reason: str = ""

    @property
    def is_computable(self) -> bool:
        return len(self.changes) > 0


def compute_opinion_change(series: dict[str, AgentStanceSeries]) -> dict[str, AgentChangeResult]:
    """Compute round-to-round opinion change for every agent in `series`.

    Section 28 requirement: "Opinion change requires multiple stance
    snapshots." This is enforced explicitly here -- an agent with 0 or 1
    stance points gets an `AgentChangeResult` with an empty `changes` list
    and a human-readable `reason`, rather than a crash or a silently wrong
    number (e.g. treating a single point as "zero change").
    """
    results: dict[str, AgentChangeResult] = {}

    for agent_id, agent_series in series.items():
        points = agent_series.points

        if len(points) == 0:
            results[agent_id] = AgentChangeResult(
                agent_id=agent_id,
                changes=[],
                reason="No stance snapshots available for this agent.",
            )
            continue

        if len(points) == 1:
            results[agent_id] = AgentChangeResult(
                agent_id=agent_id,
                changes=[],
                reason=(
                    f"Only one stance snapshot available (round {points[0].round_number}); "
                    "opinion change requires at least two."
                ),
            )
            continue

        changes = [
            OpinionChangePoint(
                agent_id=agent_id,
                from_round=points[i - 1].round_number,
                to_round=points[i].round_number,
                change=round(points[i].stance - points[i - 1].stance, 6),
            )
            for i in range(1, len(points))
        ]
        results[agent_id] = AgentChangeResult(agent_id=agent_id, changes=changes)

    return results
