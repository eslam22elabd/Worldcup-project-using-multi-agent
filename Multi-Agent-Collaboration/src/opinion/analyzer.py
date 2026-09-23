from __future__ import annotations

import math
from typing import Any

from src.opinion.models import OpinionShift, OpinionShiftType, OpinionSnapshot
from src.state.discussion_state import DiscussionState


class OpinionEvolutionAnalyzer:
    def __init__(
        self,
        polarity_threshold: float = 0.10,
    ) -> None:
        self.polarity_threshold = polarity_threshold

    def detect_shift(
        self,
        from_snapshot: OpinionSnapshot,
        to_snapshot: OpinionSnapshot,
    ) -> OpinionShift:
        p1 = from_snapshot.stance.polarity
        p2 = to_snapshot.stance.polarity
        dp = p2 - p1

        if (p1 * p2 < 0) and abs(dp) >= self.polarity_threshold:
            shift_type = OpinionShiftType.REVERSED
            explanation = (
                f"Polarity reversed from {round(p1, 2)} in round {from_snapshot.round_number} "
                f"to {round(p2, 2)} in round {to_snapshot.round_number}."
            )

        elif abs(p2) > abs(p1) + self.polarity_threshold and (p1 * p2 >= 0):
            shift_type = OpinionShiftType.STRENGTHENED
            explanation = (
                f"Opinion strengthened: polarity moved from {round(p1, 2)} "
                f"to {round(p2, 2)} (delta={round(dp, 2)})."
            )

        elif abs(p2) < abs(p1) - self.polarity_threshold and (p1 * p2 >= 0):
            shift_type = OpinionShiftType.WEAKENED
            explanation = (
                f"Opinion weakened: polarity moved from {round(p1, 2)} "
                f"to {round(p2, 2)} (delta={round(dp, 2)})."
            )

        elif abs(dp) >= self.polarity_threshold:
            shift_type = OpinionShiftType.SHIFTED
            explanation = (
                f"Position shifted from {round(p1, 2)} to {round(p2, 2)} "
                f"(delta={round(dp, 2)})."
            )
        else:
            shift_type = OpinionShiftType.UNCHANGED
            explanation = "Opinion remained stable."

        return OpinionShift(
            agent_id=to_snapshot.agent_id,
            from_round=from_snapshot.round_number,
            to_round=to_snapshot.round_number,
            shift_type=shift_type,
            delta_polarity=dp,
            explanation=explanation,
        )

    def analyze_agent_evolution(
        self,
        state: DiscussionState,
        agent_id: str,
    ) -> list[OpinionShift]:
        raw_records = state.opinions.get(agent_id, [])
        if len(raw_records) < 2:
            return []

        snapshots = [OpinionSnapshot.from_dict(r) for r in raw_records]
        snapshots.sort(key=lambda s: s.round_number)

        shifts: list[OpinionShift] = []
        for i in range(len(snapshots) - 1):
            shift = self.detect_shift(snapshots[i], snapshots[i + 1])
            shifts.append(shift)

        return shifts

    def compute_consensus_trajectory(
        self,
        state: DiscussionState,
    ) -> dict[int, dict[str, float]]:
        rounds_polarities: dict[int, list[float]] = {}

        for agent_id, records in state.opinions.items():
            for r in records:
                round_num = r.get("round", 0)
                stance_data = r.get("stance", {})
                pol = stance_data.get("polarity", 0.0)

                if round_num not in rounds_polarities:
                    rounds_polarities[round_num] = []
                rounds_polarities[round_num].append(pol)

        trajectory: dict[int, dict[str, float]] = {}

        for r_num, polarities in sorted(rounds_polarities.items()):
            n = len(polarities)
            if n == 0:
                continue

            mean_pol = sum(polarities) / n
            variance = sum((p - mean_pol) ** 2 for p in polarities) / n
            std_pol = math.sqrt(variance)
            consensus_index = max(0.0, 1.0 - std_pol)

            trajectory[r_num] = {
                "mean_polarity": round(mean_pol, 4),
                "std_polarity": round(std_pol, 4),
                "consensus_index": round(consensus_index, 4),
                "agent_count": n,
            }

        return trajectory

    def generate_evolution_report(
        self,
        state: DiscussionState,
    ) -> dict[str, Any]:
        trajectories: dict[str, list[dict[str, Any]]] = {}
        total_shifts = 0

        for agent_id in state.participants:
            agent_shifts = self.analyze_agent_evolution(state, agent_id)
            trajectories[agent_id] = [s.to_dict() for s in agent_shifts]
            for s in agent_shifts:
                if s.shift_type != OpinionShiftType.UNCHANGED:
                    total_shifts += 1

        consensus_trajectory = self.compute_consensus_trajectory(state)

        rounds = sorted(consensus_trajectory.keys())
        if len(rounds) >= 2:
            initial_consensus = consensus_trajectory[rounds[0]]["consensus_index"]
            final_consensus = consensus_trajectory[rounds[-1]]["consensus_index"]
            if final_consensus > initial_consensus + 0.05:
                trend = "converging"
            elif final_consensus < initial_consensus - 0.05:
                trend = "diverging"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "discussion_id": state.discussion_id,
            "topic": state.topic,
            "participants": list(state.participants),
            "total_rounds": state.current_round,
            "overall_trend": trend,
            "total_shifts_detected": total_shifts,
            "agent_trajectories": trajectories,
            "consensus_trajectory": {str(k): v for k, v in consensus_trajectory.items()},
        }

