"""Tests for DiscussionState — README section 20 (Discussion State),
section 17 (Discussion Run Identity), and section 16 (History Structure).
"""

from __future__ import annotations

import pytest

from src.discussion.message import Message
from src.state.discussion_state import DiscussionState, DiscussionStatus


def test_state_initialization():
    graph_config = {"nodes": ["A", "B", "C"], "edges": {"A": ["B"], "B": ["C"], "C": ["A"]}}
    state = DiscussionState(topic="World Cup Analysis", graph_config=graph_config, num_rounds=3)

    assert state.discussion_id.startswith("disc_")
    assert state.status == DiscussionStatus.INITIALIZING
    assert state.current_round == 0
    assert state.participants == ["A", "B", "C"]
    assert state.topic == "World Cup Analysis"
    assert state.messages == []
    assert set(state.opinions.keys()) == {"A", "B", "C"}
    assert state.retrieval_events == []


def test_state_lifecycle_progression():
    state = DiscussionState(topic="Tactics", participants=["A", "B"], num_rounds=3)

    state.start_round(1)
    assert state.status == DiscussionStatus.IN_PROGRESS
    assert state.current_round == 1

    state.finish_round(1)
    assert state.status == DiscussionStatus.ROUND_COMPLETE
    assert len(state.checkpoints) == 1
    assert state.checkpoints[0]["current_round"] == 1

    state.start_round(2)
    assert state.status == DiscussionStatus.IN_PROGRESS
    assert state.current_round == 2

    state.complete("Reached configured num_rounds=3.")
    assert state.status == DiscussionStatus.COMPLETED
    assert state.completed_at is not None
    assert state.termination_reason == "Reached configured num_rounds=3."


def test_message_management_and_inbox_filtering():
    state = DiscussionState(topic="Player Ratings", participants=["A", "B", "C"], num_rounds=3)

    msg1 = Message(round_number=1, sender_id="A", recipient_ids=["B"], content="Opinion 1")
    msg2 = Message(round_number=1, sender_id="B", recipient_ids=["C"], content="Opinion 2")
    msg3 = Message(round_number=2, sender_id="A", recipient_ids=["B", "C"], content="Opinion 3")

    state.add_message(msg1)
    state.add_message(msg2)
    state.add_message(msg3)

    assert len(state.messages) == 3

    # Inbox for B: received msg1 and msg3
    b_msgs = state.messages_for("B")
    assert b_msgs == [msg1, msg3]

    # Inbox for C: received msg2 and msg3
    c_msgs = state.messages_for("C")
    assert c_msgs == [msg2, msg3]

    # Inbox for A: received nothing
    assert state.messages_for("A") == []

    # Round filtering
    assert state.get_round_messages(1) == [msg1, msg2]
    assert state.get_round_messages(2) == [msg3]


def test_teammate_extension_hooks():
    state = DiscussionState(topic="Hook Test", participants=["A", "B"])

    # Teammate 3 Opinion hook
    op_record = state.record_opinion(
        agent_id="A",
        round_number=1,
        opinion="Conservative setup",
        stance={"polarity": 0.8},
        metadata={"confidence": "high"},
    )
    assert op_record["agent_id"] == "A"
    assert len(state.opinions["A"]) == 1
    assert state.opinions["A"][0]["stance"] == {"polarity": 0.8}

    # Teammate 4 Retrieval hook
    ret_record = state.record_retrieval(
        agent_id="B",
        round_number=2,
        query="Mexico 2010 squad",
        evidence=["Historical data: Rafa Marquez captain"],
        tool_name="get_knowledge",
    )
    assert ret_record["event_id"].startswith("ret_")
    assert len(state.retrieval_events) == 1
    assert state.retrieval_events[0]["query"] == "Mexico 2010 squad"


def test_to_dict_and_from_dict_lossless_roundtrip():
    state = DiscussionState(
        topic="Serialization Test",
        graph_config={"nodes": ["A", "B"], "edges": {"A": ["B"], "B": ["A"]}},
        num_rounds=3,
        metadata={"match_id": 12345},
    )
    state.start_round(1)
    msg = Message(round_number=1, sender_id="A", recipient_ids=["B"], content="Testing roundtrip")
    state.add_message(msg)
    state.record_opinion("A", 1, "Testing roundtrip")
    state.record_retrieval("A", 1, "query test", ["evidence"])
    state.complete("Finished.")

    serialized = state.to_dict()
    assert isinstance(serialized, dict)
    assert serialized["discussion_id"] == state.discussion_id
    assert serialized["status"] == DiscussionStatus.COMPLETED.value
    assert len(serialized["messages"]) == 1

    # Deserialization
    reconstructed = DiscussionState.from_dict(serialized)
    assert reconstructed.discussion_id == state.discussion_id
    assert reconstructed.topic == state.topic
    assert reconstructed.status == DiscussionStatus.COMPLETED
    assert reconstructed.current_round == 1
    assert len(reconstructed.messages) == 1
    assert reconstructed.messages[0].content == "Testing roundtrip"
    assert reconstructed.messages[0].sender_id == "A"
    assert reconstructed.messages[0].recipient_ids == ["B"]
    assert len(reconstructed.opinions["A"]) == 1
    assert len(reconstructed.retrieval_events) == 1
    assert reconstructed.metadata == {"match_id": 12345}
