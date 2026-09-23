from __future__ import annotations
from typing import Any
from src.opinion.extractor import LLMJudgeExtractor
from src.opinion.models import OpinionSnapshot, Stance
from src.state.discussion_state import DiscussionState


class OpinionTracker:
    def __init__(self, extractor: LLMJudgeExtractor | None = None) -> None:
        self.extractor = extractor or LLMJudgeExtractor()

    def record_initial_opinion(
        self,
        state: DiscussionState,
        agent_id: str,
        opinion: str,
        stance: Stance | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OpinionSnapshot:
        return self.record_round_opinion(
            state=state,
            agent_id=agent_id,
            round_number=0,
            opinion=opinion,
            topic=state.topic,
            stance=stance,
            metadata=metadata,
        )

    def record_round_opinion(
        self,
        state: DiscussionState,
        agent_id: str,
        round_number: int,
        opinion: str,
        topic: str = "",
        stance: Stance | None = None,
        context_messages: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OpinionSnapshot:
        if stance is None:
            # Build context from all messages already in state that came before
            # this agent's current round, so the judge sees the full discussion.
            ctx = context_messages if context_messages is not None else _prior_messages(
                state, round_number, agent_id
            )
            resolved_stance = self.extractor.extract(
                opinion_text=opinion,
                agent_id=agent_id,
                round_number=round_number,
                topic=topic or state.topic,
                context_messages=ctx,
            )
            extracted_automatically = True
        else:
            resolved_stance = stance
            extracted_automatically = False

        meta = dict(metadata or {})
        meta.setdefault("extracted_automatically", extracted_automatically)

        snapshot = OpinionSnapshot(
            agent_id=agent_id,
            round_number=round_number,
            opinion_text=opinion,
            stance=resolved_stance,
            metadata=meta,
        )

        state.record_opinion(
            agent_id=agent_id,
            round_number=round_number,
            opinion=opinion,
            stance=resolved_stance.to_dict(),
            metadata=meta,
        )

        return snapshot

    def get_agent_history(
        self,
        state: DiscussionState,
        agent_id: str,
    ) -> list[OpinionSnapshot]:
        raw_records = state.opinions.get(agent_id, [])
        snapshots = [OpinionSnapshot.from_dict(r) for r in raw_records]
        snapshots.sort(key=lambda s: s.round_number)
        return snapshots

    def get_round_opinions(
        self,
        state: DiscussionState,
        round_number: int,
    ) -> dict[str, OpinionSnapshot]:
        round_map: dict[str, OpinionSnapshot] = {}
        for agent_id, raw_records in state.opinions.items():
            for record in raw_records:
                if record.get("round") == round_number:
                    round_map[agent_id] = OpinionSnapshot.from_dict(record)
                    break
        return round_map

    def get_initial_opinions(self, state: DiscussionState) -> dict[str, OpinionSnapshot]:
        return self.get_round_opinions(state, round_number=0)

    def has_opinion(self, state: DiscussionState, agent_id: str, round_number: int) -> bool:
        records = state.opinions.get(agent_id, [])
        return any(r.get("round") == round_number for r in records)

    def track_from_messages(self, state: DiscussionState) -> int:
        """Walk every Message in state and record an opinion snapshot for each.

        Each call to the LLM judge includes all messages that were produced
        *before* this agent's message in the current round (i.e., the judge
        sees the full discussion context up to that point).
        """
        count = 0
        for msg in state.messages:
            if not self.has_opinion(state, msg.sender_id, msg.round_number):
                # Collect all messages sent before this one as context
                ctx = [
                    {
                        "sender_id": m.sender_id,
                        "round_number": m.round_number,
                        "content": m.content,
                    }
                    for m in state.messages
                    if m.message_id != msg.message_id
                    and (
                        m.round_number < msg.round_number
                        or (
                            m.round_number == msg.round_number
                            and m.timestamp < msg.timestamp
                        )
                    )
                ]

                self.record_round_opinion(
                    state=state,
                    agent_id=msg.sender_id,
                    round_number=msg.round_number,
                    opinion=msg.content,
                    topic=state.topic,
                    context_messages=ctx,
                    metadata={"source_message_id": msg.message_id},
                )
                count += 1
        return count


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _prior_messages(
    state: DiscussionState,
    current_round: int,
    current_agent: str,
) -> list[dict[str, Any]]:
    """Return all messages that precede the current agent's turn."""
    return [
        {
            "sender_id": m.sender_id,
            "round_number": m.round_number,
            "content": m.content,
        }
        for m in state.messages
        if m.round_number < current_round
        or (m.round_number == current_round and m.sender_id != current_agent)
    ]


