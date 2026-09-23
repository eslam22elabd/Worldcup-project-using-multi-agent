"""Discussion orchestration engine.

Implements README sections:
    9.  Discussion Orchestration -> coordinates rounds, decides which
        agent acts, what it sees, who receives its message, when the
        discussion ends.
    10. Discussion Rounds        -> at least 3 rounds of agent turns.
    21. Discussion Termination   -> a clear, minimum-viable termination
        rule (fixed number of rounds), documented and extensible.

Explicitly out of scope for this pass (later sections, not requested):
    - Mid-discussion retrieval wiring (section 14/15).
    - Persistent discussion history to disk (section 16/17).
    - Opinion evolution tracking (section 18/19).
This module only produces an in-memory, inspectable discussion trace
(a list of Message objects) — later work can persist/analyze it.

Agent contract:
    Any object implementing `DiscussionAgent` (see below) can be
    orchestrated. This keeps the orchestrator decoupled from Week 2's
    concrete `BaseAgent` implementation, so it can be adapted to real
    Week 2 agents (or any other agent) via a thin wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from src.discussion.message import Message
from src.graph.agent_graph import AgentGraph
from src.routing.router import MessageRouter
from src.state.discussion_state import DiscussionState

# Backward compatibility alias: DiscussionTrace is now backed by DiscussionState
DiscussionTrace = DiscussionState


class DiscussionAgent(Protocol):
    """Minimal interface the orchestrator needs from a participant.

    Any Week 2 agent can satisfy this by wrapping `generate_initial_opinion`
    / a new `respond_to_discussion`-style method behind `speak()`.
    """

    agent_id: str

    def speak(self, topic: str, incoming_messages: list[Message], round_number: int) -> str:
        """Produce this agent's message for the given round.

        Args:
            topic: The discussion topic.
            incoming_messages: Messages sent to this agent (from its graph
                predecessors) so far, most recent last.
            round_number: The current 1-indexed round number.

        Returns:
            The text content of this agent's message for this round.
        """
        ...


class DiscussionOrchestrator:
    """Coordinates a multi-round discussion between graph-connected agents.

    Separation of concerns:
        Agent -> Agent response -> Discussion engine -> Routing -> Other agents

    Responsibilities:
        - Orchestrates rounds (1..num_rounds, minimum 3).
        - Uses MessageRouter for inbox retrieval and recipient determination.
        - Updates and maintains the centralized DiscussionState.
        - Evaluates termination conditions cleanly.
    """

    def __init__(
        self,
        graph: AgentGraph,
        agents: dict[str, DiscussionAgent],
        num_rounds: int = 3,
        router: MessageRouter | None = None,
    ) -> None:
        if num_rounds < 3:
            raise ValueError("README section 10 requires at least 3 discussion rounds.")
        missing = set(graph.nodes) - set(agents.keys())
        if missing:
            raise ValueError(f"No agent object provided for graph node(s): {sorted(missing)}")

        self.graph = graph
        self.agents = agents
        self.num_rounds = num_rounds
        self.router = router or MessageRouter(graph)

    def run(self, topic: str) -> DiscussionState:
        """Run the full multi-round discussion and return the resulting state."""
        state = DiscussionState(
            topic=topic,
            graph_config=self.graph.as_dict(),
            participants=list(self.graph.nodes),
            num_rounds=self.num_rounds,
        )

        for round_number in range(1, self.num_rounds + 1):
            state.start_round(round_number)
            for agent_id in self.graph.nodes:
                agent = self.agents[agent_id]
                # Route incoming context to the agent
                incoming = self.router.get_agent_inbox(agent_id, state)

                # Agent produces response
                content = agent.speak(topic=topic, incoming_messages=incoming, round_number=round_number)

                # Route to graph neighbors
                recipients = self.router.determine_recipients(agent_id)
                message = Message(
                    round_number=round_number,
                    sender_id=agent_id,
                    recipient_ids=recipients,
                    content=content,
                )
                state.add_message(message)

            state.finish_round(round_number)

        state.complete(f"Reached configured num_rounds={self.num_rounds}.")
        return state
