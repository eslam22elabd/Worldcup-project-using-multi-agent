"""Graph tests — README section 26 'Graph test': verify the configured
discussion graph is strongly connected, and that a deliberately broken
graph is correctly rejected.
"""

from __future__ import annotations

import pytest

from src.graph.agent_graph import AgentGraph


def test_ring_of_four_is_strongly_connected():
    graph = AgentGraph.ring(["A", "B", "C", "D"])
    assert graph.is_strongly_connected()
    assert graph.neighbors("A") == ["B"]
    assert graph.neighbors("D") == ["A"]


def test_ring_with_shortcut_edges_stays_strongly_connected():
    graph = AgentGraph.from_edges(
        agent_ids=["A", "B", "C", "D"],
        extra_edges=[("A", "C"), ("D", "B")],
    )
    assert graph.is_strongly_connected()
    # base ring edge plus the shortcut both present
    assert set(graph.neighbors("A")) == {"B", "C"}


def test_two_agents_form_a_valid_ring():
    graph = AgentGraph.ring(["A", "B"])
    assert graph.is_strongly_connected()
    assert graph.neighbors("A") == ["B"]
    assert graph.neighbors("B") == ["A"]


def test_single_agent_is_rejected():
    with pytest.raises(ValueError):
        AgentGraph.ring(["A"])


def test_directly_constructing_a_non_strongly_connected_graph_is_rejected():
    # A -> B -> C with no way back to A: not strongly connected.
    broken = AgentGraph(nodes=["A", "B", "C"], edges={"A": ["B"], "B": ["C"], "C": []})
    assert not broken.is_strongly_connected()


def test_as_dict_is_inspectable_and_reproducible():
    graph = AgentGraph.ring(["A", "B", "C"])
    snapshot = graph.as_dict()
    assert snapshot == {
        "nodes": ["A", "B", "C"],
        "edges": {"A": ["B"], "B": ["C"], "C": ["A"]},
    }
    # Rebuilding from the same node list reproduces an equivalent graph.
    rebuilt = AgentGraph.ring(["A", "B", "C"])
    assert rebuilt.as_dict() == snapshot
