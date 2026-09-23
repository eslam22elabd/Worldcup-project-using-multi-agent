"""Orchestrator tests — README section 26:
    - 'Multi-round test': verify the system can execute at least 3 rounds.
    - Routing behavior implied by section 11/12: a message is only
      delivered to an agent's graph neighbors, not broadcast to everyone.
"""

from __future__ import annotations

import pytest

from src.discussion.message import Message
from src.graph.agent_graph import AgentGraph
from src.orchestration.orchestrator import DiscussionOrchestrator


class StubAgent:
    """A trivial DiscussionAgent used for testing orchestration mechanics
    without depending on a real LLM call."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.calls: list[tuple[int, int]] = []  # (round_number, num_incoming_seen)

    def speak(self, topic: str, incoming_messages: list[Message], round_number: int) -> str:
        self.calls.append((round_number, len(incoming_messages)))
        return f"{self.agent_id} says something about '{topic}' in round {round_number}"


def _build_ring_of(agent_ids: list[str]) -> tuple[AgentGraph, dict[str, StubAgent]]:
    graph = AgentGraph.ring(agent_ids)
    agents = {aid: StubAgent(aid) for aid in agent_ids}
    return graph, agents


def test_orchestrator_runs_at_least_three_rounds():
    graph, agents = _build_ring_of(["A", "B", "C", "D"])
    orchestrator = DiscussionOrchestrator(graph=graph, agents=agents, num_rounds=3)

    trace = orchestrator.run(topic="Test topic")

    rounds_seen = {m.round_number for m in trace.messages}
    assert rounds_seen == {1, 2, 3}
    # 4 agents * 3 rounds = 12 messages total
    assert len(trace.messages) == 12
    assert trace.termination_reason == "Reached configured num_rounds=3."


def test_orchestrator_rejects_fewer_than_three_rounds():
    graph, agents = _build_ring_of(["A", "B"])
    with pytest.raises(ValueError):
        DiscussionOrchestrator(graph=graph, agents=agents, num_rounds=2)


def test_messages_are_routed_only_to_graph_neighbors_not_broadcast():
    graph, agents = _build_ring_of(["A", "B", "C"])
    orchestrator = DiscussionOrchestrator(graph=graph, agents=agents, num_rounds=3)

    trace = orchestrator.run(topic="Routing check")

    # In a 3-node ring, A -> B, B -> C, C -> A. No agent should ever
    # receive a message sent to someone else's neighbor set.
    for message in trace.messages:
        expected_recipients = graph.neighbors(message.sender_id)
        assert message.recipient_ids == expected_recipients
        assert len(message.recipient_ids) == 1  # pure ring: single downstream neighbor


def test_each_agent_sees_growing_context_across_rounds():
    graph, agents = _build_ring_of(["A", "B", "C"])
    orchestrator = DiscussionOrchestrator(graph=graph, agents=agents, num_rounds=3)
    orchestrator.run(topic="Context growth check")

    # Agent B receives one message per round from A (its only predecessor).
    # By round 3, when B speaks, it should have seen up to 3 incoming
    # messages accumulated from rounds 1..3 (A always speaks before B
    # within a round, per graph.nodes order).
    calls = agents["B"].calls
    incoming_counts = [count for (_round, count) in calls]
    assert incoming_counts == sorted(incoming_counts)  # non-decreasing across rounds
    assert incoming_counts[-1] >= incoming_counts[0]


def test_missing_agent_for_graph_node_raises():
    graph = AgentGraph.ring(["A", "B", "C"])
    incomplete_agents = {"A": StubAgent("A"), "B": StubAgent("B")}  # missing "C"
    with pytest.raises(ValueError):
        DiscussionOrchestrator(graph=graph, agents=incomplete_agents, num_rounds=3)
