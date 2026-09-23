"""Tests for MessageRouter — README section 11 (Message Routing),
section 12 (Routing Requirements), and section 13 (Agent Context).
"""

from __future__ import annotations

import pytest

from src.discussion.message import Message
from src.graph.agent_graph import AgentGraph
from src.routing.router import MessageRouter
from src.state.discussion_state import DiscussionState


def test_ring_routing_single_neighbor():
    graph = AgentGraph.ring(["A", "B", "C", "D"])
    router = MessageRouter(graph)

    recipients_a = router.determine_recipients("A")
    assert recipients_a == ["B"]

    recipients_d = router.determine_recipients("D")
    assert recipients_d == ["A"]


def test_shortcut_routing_multi_neighbor():
    graph = AgentGraph.from_edges(
        agent_ids=["A", "B", "C", "D"],
        extra_edges=[("A", "C"), ("A", "D")],
    )
    router = MessageRouter(graph)

    recipients_a = router.determine_recipients("A")
    assert set(recipients_a) == {"B", "C", "D"}

    recipients_b = router.determine_recipients("B")
    assert recipients_b == ["C"]


def test_unknown_sender_raises_value_error():
    graph = AgentGraph.ring(["A", "B"])
    router = MessageRouter(graph)

    with pytest.raises(ValueError, match="does not exist in graph nodes"):
        router.determine_recipients("Z")


def test_no_leakage_to_unconnected_agents():
    # 3-agent ring: A -> B -> C -> A
    graph = AgentGraph.ring(["A", "B", "C"])
    router = MessageRouter(graph)
    state = DiscussionState(topic="Tactics", graph_config=graph.as_dict(), participants=graph.nodes)

    msg_from_a = Message(round_number=1, sender_id="A", recipient_ids=router.determine_recipients("A"), content="Msg from A")
    state.add_message(msg_from_a)

    # Only B is in msg_from_a recipients
    inbox_b = router.get_agent_inbox("B", state)
    inbox_c = router.get_agent_inbox("C", state)
    inbox_a = router.get_agent_inbox("A", state)

    assert len(inbox_b) == 1
    assert inbox_b[0].content == "Msg from A"
    assert len(inbox_c) == 0
    assert len(inbox_a) == 0


def test_inbox_order_and_round_filtering():
    graph = AgentGraph.ring(["A", "B"])
    router = MessageRouter(graph)
    state = DiscussionState(topic="Analysis", graph_config=graph.as_dict(), participants=graph.nodes)

    # Round 1
    state.start_round(1)
    msg1 = Message(round_number=1, sender_id="A", recipient_ids=["B"], content="Round 1 Msg")
    state.add_message(msg1)

    # Round 2
    state.start_round(2)
    msg2 = Message(round_number=2, sender_id="A", recipient_ids=["B"], content="Round 2 Msg")
    state.add_message(msg2)

    # Cumulative inbox
    all_incoming = router.get_agent_inbox("B", state, current_round_only=False)
    assert len(all_incoming) == 2
    assert [m.content for m in all_incoming] == ["Round 1 Msg", "Round 2 Msg"]

    # Current round only
    round2_only = router.get_agent_inbox("B", state, current_round_only=True)
    assert len(round2_only) == 1
    assert round2_only[0].content == "Round 2 Msg"


def test_context_formatting():
    graph = AgentGraph.ring(["A", "B"])
    router = MessageRouter(graph)

    # Empty context
    empty_context = router.format_agent_context("B", [])
    assert "No previous messages" in empty_context

    # Populated context
    messages = [
        Message(round_number=1, sender_id="A", recipient_ids=["B"], content="VAEP analysis indicates strong play."),
        Message(round_number=2, sender_id="A", recipient_ids=["B"], content="Second half pressure dropped."),
    ]
    formatted = router.format_agent_context("B", messages)
    assert "Analyst 'A'" in formatted
    assert "[Round 1]" in formatted
    assert "[Round 2]" in formatted
    assert "VAEP analysis indicates strong play." in formatted
    assert "Second half pressure dropped." in formatted


def test_custom_routing_filter():
    graph = AgentGraph.from_edges(
        agent_ids=["A", "B", "C"],
        extra_edges=[("A", "C")],
    )
    router = MessageRouter(graph)

    # A ordinarily routes to B and C
    assert set(router.determine_recipients("A")) == {"B", "C"}

    # Register filter: exclude C if metadata flag 'exclude_c' is True
    def exclude_c_filter(sender: str, recipients: list[str], meta: dict) -> list[str]:
        if meta.get("exclude_c"):
            return [r for r in recipients if r != "C"]
        return recipients

    router.register_filter(exclude_c_filter)

    assert set(router.determine_recipients("A", metadata={"exclude_c": True})) == {"B"}
    assert set(router.determine_recipients("A", metadata={"exclude_c": False})) == {"B", "C"}
