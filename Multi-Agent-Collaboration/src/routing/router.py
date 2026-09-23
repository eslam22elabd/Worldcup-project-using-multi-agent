"""Graph-based message routing engine.

Decouples routing logic from the orchestration loop:
    Agent -> Agent response -> Discussion engine -> Routing -> Other agents
"""

from __future__ import annotations

from typing import Any, Callable

from src.discussion.message import Message
from src.graph.agent_graph import AgentGraph
from src.state.discussion_state import DiscussionState

# Type alias for custom routing filter: (sender_id, candidate_recipients, metadata) -> filtered_recipients
RoutingFilter = Callable[[str, list[str], dict[str, Any]], list[str]]


class MessageRouter:
    """Routes messages between agents based on the communication graph.

    Responsibilities:
        - Resolves message recipients according to graph outgoing edges.
        - Prevents arbitrary broadcasting by enforcing topological relationships.
        - Manages per-agent inbox retrieval (cumulative or round-specific).
        - Assembles incoming context prompts preserving sender identity and rounds.
        - Provides extensibility filters for conditional or selective routing.
    """

    def __init__(self, graph: AgentGraph) -> None:
        self.graph = graph
        self._filters: list[RoutingFilter] = []

    # ------------------------------------------------------------------
    # Recipient Resolution
    # ------------------------------------------------------------------

    def determine_recipients(
        self,
        sender_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[str]:
        """Determine recipient agent IDs for a message from `sender_id`.

        Uses outgoing edges in the agent graph (`graph.neighbors(sender_id)`).
        If any custom routing filters are registered, they are evaluated
        sequentially to refine the recipient list.

        Args:
            sender_id: The ID of the sending agent.
            metadata: Optional message metadata that filters can evaluate.

        Returns:
            List of recipient agent IDs.

        Raises:
            ValueError: if sender_id is not in the graph.
        """
        if sender_id not in self.graph.nodes:
            raise ValueError(
                f"Sender '{sender_id}' does not exist in graph nodes: {self.graph.nodes}"
            )

        recipients = list(self.graph.neighbors(sender_id))
        meta = metadata or {}

        # Apply registered routing filters if any
        for fltr in self._filters:
            recipients = fltr(sender_id, recipients, meta)

        return recipients

    def register_filter(self, filter_fn: RoutingFilter) -> None:
        """Register a custom routing filter for conditional routing."""
        self._filters.append(filter_fn)

    # ------------------------------------------------------------------
    # Inbox Management
    # ------------------------------------------------------------------

    def get_agent_inbox(
        self,
        agent_id: str,
        state: DiscussionState,
        current_round_only: bool = False,
    ) -> list[Message]:
        """Retrieve all messages routed to `agent_id` from discussion state.

        Args:
            agent_id: The recipient agent ID.
            state: The current DiscussionState.
            current_round_only: If True, only messages from state.current_round
                are returned. If False, returns all historical messages routed
                to this agent across all rounds.

        Returns:
            Chronologically ordered list of Message instances.
        """
        inbox = state.messages_for(agent_id)
        if current_round_only:
            inbox = [m for m in inbox if m.round_number == state.current_round]
        return inbox


    def format_agent_context(
        self,
        agent_id: str,
        incoming_messages: list[Message],
    ) -> str:
        """Format an agent's incoming messages into structured context.

        Preserves sender identity, round numbers, and content order,
        ensuring the agent can react coherently to its graph neighbors.

        Args:
            agent_id: The receiving agent ID.
            incoming_messages: Messages delivered to this agent.

        Returns:
            Formatted string representation for prompting the agent.
        """
        if not incoming_messages:
            return "No previous messages from other analysts."

        lines = [
            f"Here are the messages routed to you from other analysts ({len(incoming_messages)} total):"
        ]
        for msg in incoming_messages:
            lines.append(
                f"\n--- [Round {msg.round_number}] Analyst '{msg.sender_id}' ---"
            )
            lines.append(f"{msg.content}")

        lines.append(
            "\nConsidering the above viewpoints alongside your own evidence, "
            "provide your analytical perspective (maintaining, refining, or revising your stance)."
        )
        return "\n".join(lines)
