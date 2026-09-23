"""Influence scoring.

------------------------------------------------------------------------
DeGroot-Inspired Correlation Formulation
------------------------------------------------------------------------
The DeGroot model says agents update opinions as weighted averages of
their neighbors' opinions.  We measure whether that pattern holds in
the actual data using correlation.

For each agent i that SENDS messages to peers, we collect observation
pairs (X, Y) across all rounds r where both endpoints have data:

    X = s_i(r) - s_j(r)          "stance pull"
        The difference between sender i's stance and recipient j's
        stance in round r.  Positive means i is above j; negative
        means i is below j.

    Y = s_j(r+1) - s_j(r)        "recipient's subsequent change"
        How much recipient j's stance changed from round r to r+1.

If agent i is influential in a DeGroot sense, peers tend to move
TOWARD i's position:  when X > 0 (i is above j), Y > 0 (j moves up),
and when X < 0 (i is below j), Y < 0 (j moves down).  This gives a
positive correlation between X and Y.

The influence score is the cosine similarity of the (X, Y) vectors:

    influence(i) = dot(X, Y) / (||X|| * ||Y||)

This equals the Pearson correlation when X and Y are centered, but
here we intentionally do NOT center them because the natural zero
points (X=0 means "same stance", Y=0 means "no change") are already
meaningful anchors.  Centering would lose the directional
interpretation.

Range:  [-1.0, 1.0]
    +1.0 = perfect positive influence: peers always move toward i.
     0.0 = no association between i's stance pull and peer changes.
    -1.0 = perfect contrarian effect: peers always move AWAY from i.

Edge cases handled (section 16):
    - < 2 rounds total: cannot observe post-message changes.
    - Agent has no outgoing interactions: no observations.
    - All X values are zero: sender always has same stance as peers.
    - All Y values are zero: no peer changes observed.
    - Only 1 observation pair: insufficient for correlation.
    In all cases: score = None, is_computable = False, with reason.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any
import json
from pathlib import Path
from src.ingestion.discussion_loader import LoadedDiscussion
from src.opinion_change.stance_series import AgentStanceSeries


@dataclass
class AgentInfluenceResult:
    """Influence result for one agent.

    Attributes:
        agent_id: The agent this score belongs to.
        score: The influence score in [-1.0, 1.0], or None if not
            computable.
        is_computable: Whether a meaningful score could be calculated.
        reason: Why the score is not computable (empty if it is).
        num_observations: How many (X, Y) pairs were collected.
    """

    agent_id: str
    score: float | None
    is_computable: bool
    reason: str = ""
    num_observations: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to section 19 format: {"agent_id": score_or_null}."""
        return {
            "score": round(self.score, 4) if self.score is not None else None,
            "is_computable": self.is_computable,
            "reason": self.reason,
            "num_observations": self.num_observations,
        }


def _extract_interactions(discussion: LoadedDiscussion) -> list[dict[str, Any]]:
    """Extract directed interactions from the discussion's round messages.

    Each interaction is:
        {"round": int, "sender": str, "recipient": str}

    Prioritizes:
      1. discussion.rounds_data and discussion.graph_data (retained in-memory on LoadedDiscussion).
      2. Re-reading from discussion.source_path / discussion._source_path if available.
      3. Fallback to searching bundled data/sample directory if ID matches sample.
    """
    import json
    from pathlib import Path

    interactions: list[dict[str, Any]] = []

    # 1. First check in-memory rounds_data and graph_data from LoadedDiscussion
    rounds_data: dict[str, Any] = getattr(discussion, "rounds_data", {}) or {}
    graph_data: dict[str, Any] = getattr(discussion, "graph_data", {}) or {}

    # 2. If not present in memory, attempt to read via source_path
    if not rounds_data and not graph_data:
        source_path = getattr(discussion, "source_path", "") or getattr(discussion, "_source_path", "")
        if source_path:
            try:
                p = Path(source_path)
                if p.exists() and p.is_file():
                    raw_data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(raw_data, dict):
                        rounds_data = raw_data.get("rounds") if isinstance(raw_data.get("rounds"), dict) else {}
                        graph_data = raw_data.get("graph") if isinstance(raw_data.get("graph"), dict) else {}
            except Exception:
                pass

    # 3. Fallback: try searching the default sample path
    if not rounds_data and not graph_data:
        default_sample = Path(__file__).resolve().parents[2] / "data" / "sample"
        for f in default_sample.glob(f"*{discussion.discussion_id}*"):
            try:
                raw_data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(raw_data, dict):
                    rounds_data = raw_data.get("rounds") if isinstance(raw_data.get("rounds"), dict) else {}
                    graph_data = raw_data.get("graph") if isinstance(raw_data.get("graph"), dict) else {}
                    if rounds_data or graph_data:
                        break
            except Exception:
                continue

    # Extract interactions from per-round messages (more granular)
    if rounds_data and isinstance(rounds_data, dict):
        for round_key, messages in rounds_data.items():
            if not isinstance(messages, list):
                continue
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                sender = msg.get("sender", "")
                recipients = msg.get("recipients", [])
                round_num = msg.get("round")
                if round_num is None:
                    # Parse from key like "round_1"
                    try:
                        round_num = int(round_key.split("_")[-1])
                    except (ValueError, IndexError):
                        continue
                for recipient in recipients:
                    interactions.append({
                        "round": int(round_num),
                        "sender": sender,
                        "recipient": recipient,
                    })
        if interactions:
            return interactions

    # Fallback: use static graph edges across all available rounds
    if graph_data and isinstance(graph_data, dict):
        edges = graph_data.get("edges", {})
        max_round = discussion.num_rounds or 1
        for sender, recipients in edges.items():
            if not isinstance(recipients, list):
                continue
            for recipient in recipients:
                for r in range(1, max_round + 1):
                    interactions.append({
                        "round": r,
                        "sender": sender,
                        "recipient": recipient,
                    })

    return interactions


def compute_influence(
    series: dict[str, AgentStanceSeries],
    discussion: LoadedDiscussion,
) -> dict[str, AgentInfluenceResult]:
    """Compute per-agent influence scores (sections 12-16).

    For each agent that sends messages, we collect (X, Y) pairs:
        X = sender_stance(r) - recipient_stance(r)     ("stance pull")
        Y = recipient_stance(r+1) - recipient_stance(r) ("peer change")

    The influence score is the cosine similarity of the X and Y vectors.
    See module docstring for the full formulation.

    Args:
        series: Per-agent stance series (from build_stance_series).
        discussion: The loaded discussion (for extracting interactions).

    Returns:
        A dict mapping agent_id -> AgentInfluenceResult for every agent.
    """
    results: dict[str, AgentInfluenceResult] = {}

    # Determine available rounds from the data.
    all_rounds: set[int] = set()
    for agent_series in series.values():
        for p in agent_series.points:
            all_rounds.add(p.round_number)

    if len(all_rounds) < 2:
        # Section 16: need at least 2 rounds to observe post-message changes.
        for agent_id in series:
            results[agent_id] = AgentInfluenceResult(
                agent_id=agent_id,
                score=None,
                is_computable=False,
                reason=(
                    "Influence requires at least 2 rounds to observe "
                    "post-message opinion changes; found "
                    f"{len(all_rounds)} round(s)."
                ),
            )
        return results

    # Extract directed interactions from messages / graph.
    interactions = _extract_interactions(discussion)

    # Build a lookup: sender -> list of (round, recipient).
    sender_interactions: dict[str, list[tuple[int, str]]] = {}
    for ix in interactions:
        sender = ix["sender"]
        sender_interactions.setdefault(sender, []).append(
            (ix["round"], ix["recipient"])
        )

    # Compute influence for each agent.
    for agent_id in series:
        agent_ixs = sender_interactions.get(agent_id, [])

        if not agent_ixs:
            results[agent_id] = AgentInfluenceResult(
                agent_id=agent_id,
                score=None,
                is_computable=False,
                reason="Agent has no outgoing communication interactions.",
            )
            continue

        # Collect (X, Y) observation pairs.
        x_vals: list[float] = []
        y_vals: list[float] = []

        for round_num, recipient in agent_ixs:
            sender_series = series.get(agent_id)
            recip_series = series.get(recipient)
            if sender_series is None or recip_series is None:
                continue

            # Sender's stance in the round they spoke.
            s_sender = sender_series.stance_at(round_num)
            # Recipient's stance in the same round (before update).
            s_recip_before = recip_series.stance_at(round_num)
            # Recipient's stance in the NEXT round (after hearing sender).
            s_recip_after = recip_series.stance_at(round_num + 1)

            if s_sender is None or s_recip_before is None or s_recip_after is None:
                continue

            x = s_sender - s_recip_before       # stance pull
            y = s_recip_after - s_recip_before   # peer's subsequent change

            x_vals.append(x)
            y_vals.append(y)

        n_obs = len(x_vals)

        if n_obs == 0:
            results[agent_id] = AgentInfluenceResult(
                agent_id=agent_id,
                score=None,
                is_computable=False,
                reason=(
                    "No usable observation pairs: sender and/or recipients "
                    "lack stance data in consecutive rounds."
                ),
            )
            continue

        if n_obs < 2:
            results[agent_id] = AgentInfluenceResult(
                agent_id=agent_id,
                score=None,
                is_computable=False,
                reason=(
                    "Only 1 observation pair available; need at least 2 "
                    "for a meaningful correlation."
                ),
                num_observations=n_obs,
            )
            continue

        # Cosine similarity:  dot(X,Y) / (||X|| * ||Y||)
        dot_xy = sum(a * b for a, b in zip(x_vals, y_vals))
        norm_x = math.sqrt(sum(a * a for a in x_vals))
        norm_y = math.sqrt(sum(b * b for b in y_vals))

        if norm_x < 1e-12:
            # All X values ~ 0: sender always had the same stance as peers.
            results[agent_id] = AgentInfluenceResult(
                agent_id=agent_id,
                score=None,
                is_computable=False,
                reason=(
                    "Sender's stance was effectively identical to all "
                    "recipients in every observed round (zero stance pull)."
                ),
                num_observations=n_obs,
            )
            continue

        if norm_y < 1e-12:
            # All Y values ~ 0: no peer stance changes observed.
            results[agent_id] = AgentInfluenceResult(
                agent_id=agent_id,
                score=None,
                is_computable=False,
                reason=(
                    "No opinion changes observed in recipient peers "
                    "across the observed rounds."
                ),
                num_observations=n_obs,
            )
            continue

        score = round(dot_xy / (norm_x * norm_y), 6)

        results[agent_id] = AgentInfluenceResult(
            agent_id=agent_id,
            score=score,
            is_computable=True,
            num_observations=n_obs,
        )

    return results
