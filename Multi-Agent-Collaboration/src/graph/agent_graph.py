"""Agent communication graph.

Implements README sections 6-8:
    6. Agent Graph          -> nodes = agents, edges = communication links,
                                must be strongly connected.
    7. Graph Requirements   -> inspectable / reproducible graph config.
    8. Graph Design         -> deliberate, documented construction strategy.

Design decision (documented per section 8):
    The graph is built as a **directed cycle ("ring") plus optional extra
    shortcut edges**.

    Why a directed cycle as the base structure:
        - A directed cycle over N agents (A -> B -> C -> ... -> A) is the
          *minimal* graph that is guaranteed to be strongly connected for
          any N >= 2, using exactly N edges. Every agent can reach every
          other agent by walking forward around the ring.
        - It is trivial to reason about and to reproduce: the graph is
          fully determined by the ordered list of agent ids.
        - It naturally supports round-robin-style discussion (see
          src/orchestration/orchestrator.py), since each agent has exactly
          one designated "downstream" recipient in the base structure.

    Why allow extra shortcut edges on top:
        - A pure ring makes every agent's discussion context depend only
          on its single predecessor, which can be too restrictive for a
          richer discussion (e.g. persona-based relationships, section 8's
          "similarity-based relationships" option).
        - Extra directed edges (agent -> agent) can be added manually or
          generated (e.g. from persona similarity) without ever breaking
          strong connectivity, because the base ring already guarantees a
          path between every pair of agents; extra edges can only add
          reachability, never remove it.

    How strong connectivity is guaranteed:
        - Enforced constructively (the base ring already satisfies the
          definition), and additionally verified explicitly via
          `is_strongly_connected()`, which every constructor path runs
          before returning the graph. This makes connectivity a checked
          invariant, not just an assumption.

    How the graph affects discussion behavior:
        - `neighbors(agent_id)` (outgoing edges) is used by the
          orchestrator's routing logic (README section 11) to decide who
          receives an agent's message each round. Agents with more
          outgoing edges (e.g. from added shortcuts) influence more of the
          discussion per round; agents with more incoming edges receive
          more context to react to.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class AgentGraph:
    """A directed graph of participating agents.

    Nodes are agent ids (str). Edges are directed communication links:
    an edge ``a -> b`` means "a message from a is routed to b".

    Attributes:
        nodes: Ordered list of agent ids participating in the discussion.
        edges: Adjacency map {agent_id: [downstream_agent_id, ...]}.
    """

    nodes: list[str] = field(default_factory=list)
    edges: dict[str, list[str]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def ring(cls, agent_ids: list[str]) -> "AgentGraph":
        """Build the base strongly-connected structure: a directed cycle.

        agent_ids[0] -> agent_ids[1] -> ... -> agent_ids[-1] -> agent_ids[0]

        Raises:
            ValueError: if fewer than 2 agents are given (a graph of 1
                node is trivially "strongly connected" but cannot host a
                discussion between multiple perspectives).
        """
        if len(agent_ids) < 2:
            raise ValueError("A discussion graph needs at least 2 agents.")

        edges: dict[str, list[str]] = {a: [] for a in agent_ids}
        for i, a in enumerate(agent_ids):
            downstream = agent_ids[(i + 1) % len(agent_ids)]
            edges[a].append(downstream)

        graph = cls(nodes=list(agent_ids), edges=edges)
        graph._assert_strongly_connected()
        return graph

    @classmethod
    def from_edges(cls, agent_ids: list[str], extra_edges: list[tuple[str, str]]) -> "AgentGraph":
        """Build a ring, then add manually-specified extra directed edges.

        This is the entry point for "manually configured relationships"
        or "persona-based relationships" (section 8) layered on top of the
        connectivity-guaranteeing ring.

        Args:
            agent_ids: Ordered list of participating agent ids.
            extra_edges: Additional (from_id, to_id) directed edges to add
                on top of the base ring. Duplicate or self-loop edges are
                ignored.
        """
        graph = cls.ring(agent_ids)
        for src, dst in extra_edges:
            if src not in graph.nodes or dst not in graph.nodes:
                raise ValueError(f"Edge ({src!r} -> {dst!r}) references an unknown agent id.")
            if src == dst:
                continue
            if dst not in graph.edges[src]:
                graph.edges[src].append(dst)
        graph._assert_strongly_connected()
        return graph

    # ------------------------------------------------------------------
    # Inspection / routing
    # ------------------------------------------------------------------

    def neighbors(self, agent_id: str) -> list[str]:
        """Return the agents that directly receive messages from ``agent_id``."""
        return list(self.edges.get(agent_id, []))

    def as_dict(self) -> dict:
        """Return an inspectable, JSON-serializable representation of the graph.

        Satisfies section 7's "inspectable or reproducible" requirement.
        """
        return {"nodes": list(self.nodes), "edges": {k: list(v) for k, v in self.edges.items()}}

    # ------------------------------------------------------------------
    # Strong connectivity check
    # ------------------------------------------------------------------

    def _reachable_from(self, start: str, edges: dict[str, list[str]]) -> set[str]:
        seen = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for nxt in edges.get(current, []):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    def _reversed_edges(self) -> dict[str, list[str]]:
        reversed_edges: dict[str, list[str]] = {n: [] for n in self.nodes}
        for src, dsts in self.edges.items():
            for dst in dsts:
                reversed_edges[dst].append(src)
        return reversed_edges

    def is_strongly_connected(self) -> bool:
        """Verify every node can reach, and be reached from, every other node.

        Implementation: pick an arbitrary start node, then confirm it can
        reach all other nodes via forward edges AND can be reached from all
        other nodes via forward edges (equivalently: all nodes are
        reachable from start in the reversed graph). This is a standard
        O(V+E) two-pass reachability check, sufficient for the graph sizes
        used in this project (a handful of agents).
        """
        if not self.nodes:
            return True
        start = self.nodes[0]
        forward_reachable = self._reachable_from(start, self.edges)
        backward_reachable = self._reachable_from(start, self._reversed_edges())
        all_nodes = set(self.nodes)
        return forward_reachable == all_nodes and backward_reachable == all_nodes

    def _assert_strongly_connected(self) -> None:
        if not self.is_strongly_connected():
            raise ValueError(
                "Constructed agent graph is not strongly connected. "
                f"Graph: {self.as_dict()}"
            )
