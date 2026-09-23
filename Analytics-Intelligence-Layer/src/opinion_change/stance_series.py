"""Numeric stance representation.

Implements README sections:
    6. Opinion Change (required output) -> a per-agent, per-round numeric
       stance series.
    7. Representing Opinions Numerically -> document what the number
       means, its range, and how it was derived.

--------------------------------------------------------------------
Documented choice for section 7
--------------------------------------------------------------------
What does the stance value represent?
    It is REUSED directly from Week 3's own `Stance.polarity`, rather
    than recomputed here. Week 3 already derives a numeric polarity for
    every opinion snapshot (via a lexical heuristic over the opinion
    text -- see Week 3's `src/opinion/extractor.py`), and README section
    4 explicitly instructs this repo to "consume the existing discussion
    data rather than recreating the discussion process". Recomputing our
    own stance score from the same text would be exactly that kind of
    duplication, and would produce two disagreeing numbers for the same
    opinion with no clear reason to prefer one.

What is its range?
    [-1.0, 1.0] (values outside this range in the source data are
    clamped during validation -- see `discussion_loader.py`).

What does a higher value mean?
    The opinion's language leaned more toward favorable/positive framing
    of whatever it was discussing (per Week 3's positive/negative lexical
    word lists).

What does a lower value mean?
    The opinion's language leaned more toward critical/negative framing.
    A value near 0.0 means either neutral language or no strong lexical
    signal either way (these two cases are NOT distinguishable from the
    polarity number alone -- a genuine limitation of a lexical heuristic,
    documented here rather than papered over).

How is an opinion converted into the value?
    Not converted here at all -- taken as-is from Week 3's
    `opinion_history[agent_id][i].stance.polarity`.

How should the value be interpreted across rounds?
    As a RELATIVE signal for a single agent's own trajectory, not an
    absolute measure of "how correct" or "how strong" an opinion is.
    Comparing polarity *across different agents* is weaker evidence than
    comparing one agent's polarity *across its own rounds*, since the
    heuristic only counts word matches and has no notion of the specific
    claim being debated.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.ingestion.discussion_loader import LoadedDiscussion, OpinionSnapshotRecord


@dataclass
class StancePoint:
    """One (round, stance) data point for a single agent."""

    round_number: int
    stance: float


@dataclass
class AgentStanceSeries:
    """An agent's full stance trajectory, sorted by round.

    `points` only contains rounds that actually had usable data --
    missing rounds are simply absent, not filled with a placeholder
    value (see module docstring / README section 28 on missing data:
    inventing a 0.0 for a missing round would silently misrepresent "no
    data" as "neutral opinion", which is exactly the kind of silent
    incorrect result section 27 asks us to avoid).
    """

    agent_id: str
    points: list[StancePoint]

    @property
    def has_data(self) -> bool:
        return len(self.points) > 0

    def stance_at(self, round_number: int) -> float | None:
        for p in self.points:
            if p.round_number == round_number:
                return p.stance
        return None


def build_stance_series(discussion: LoadedDiscussion) -> dict[str, AgentStanceSeries]:
    """Build the per-agent, per-round stance series required by section 6.

    Every agent in `discussion.participants` gets an entry, even if it has
    zero usable stance points (an empty `AgentStanceSeries` -- see
    `has_data`), so the caller can distinguish "this agent had no data" from
    "this agent doesn't exist", per section 28's requirement to explicitly
    handle insufficient data rather than silently omitting the agent.
    """
    by_agent: dict[str, list[OpinionSnapshotRecord]] = {agent_id: [] for agent_id in discussion.participants}
    for snapshot in discussion.snapshots:
        by_agent.setdefault(snapshot.agent_id, []).append(snapshot)

    series: dict[str, AgentStanceSeries] = {}
    for agent_id, records in by_agent.items():
        sorted_records = sorted(records, key=lambda r: r.round_number)
        points = [StancePoint(round_number=r.round_number, stance=r.stance) for r in sorted_records]
        series[agent_id] = AgentStanceSeries(agent_id=agent_id, points=points)

    return series
