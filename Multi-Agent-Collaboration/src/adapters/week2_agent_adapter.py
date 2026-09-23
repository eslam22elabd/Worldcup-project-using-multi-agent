"""Week 2 agent adapter.

Wraps a real Week 2 `BaseAgent` (persona + LLM + tools + memory) so it can
participate in this project's `DiscussionOrchestrator`, which only
requires an object with an `agent_id` attribute and a `speak(...)` method
(see `src.orchestration.orchestrator.DiscussionAgent`).

Integration approach: same "sibling repo, direct Python import" pattern
used for the Week 1 <-> Week 2 integration (see Week 2's
`knowledge_retrieval_tool.py`). Both Week 2 and this Week 3 repo use `src`
as their top-level package name, so a naive `sys.path` insertion is not
enough — Python would resolve `src` to whichever package was imported
first in this process. `_import_week2_module()` below evicts this
project's own cached `src.*` modules for the duration of the import, then
restores them, exactly like the Week 1/2 fix.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from src.discussion.message import Message

# ---------------------------------------------------------------------------
# Locate the Week 2 repo. Default assumption: sibling folder next to this
# project, e.g.
#   projects/
#     Multi-Agent-Collaboration-main/     <- this repo
#     Intelligent-Agent-Framework-week2/  <- Week 2 repo
# Override with WEEK2_PROJECT_PATH if your layout differs.
# ---------------------------------------------------------------------------
_DEFAULT_WEEK2_PATH = Path(__file__).resolve().parents[3] / "Intelligent-Agent-Framework-week2"
_WEEK2_PATH = Path(os.getenv("WEEK2_PROJECT_PATH", str(_DEFAULT_WEEK2_PATH))).resolve()
_WEEK2_PERSONAS_DIR = _WEEK2_PATH / "personas"


def _import_week2_module(module_name: str):
    """Import a module from the Week 2 repo, working around the fact that
    both repos use `src` as their top-level package name (see module
    docstring for why a plain sys.path insert is not sufficient)."""
    import importlib

    saved_modules = {
        name: mod for name, mod in sys.modules.items() if name == "src" or name.startswith("src.")
    }
    for name in saved_modules:
        del sys.modules[name]

    if str(_WEEK2_PATH) in sys.path:
        sys.path.remove(str(_WEEK2_PATH))
    sys.path.insert(0, str(_WEEK2_PATH))

    try:
        module = importlib.import_module(module_name)
    finally:
        for name in list(sys.modules):
            if name == "src" or name.startswith("src."):
                del sys.modules[name]
        sys.modules.update(saved_modules)

    return module


class Week2AgentAdapter:
    """Adapts a Week 2 `BaseAgent` to this project's `DiscussionAgent` protocol.

    Behavior:
        - First call to `speak()` (round 1, no incoming messages yet) uses
          the agent's own `generate_initial_opinion()` — same call Week
          2's `main.py` uses to produce the initial per-agent opinion.
        - Every subsequent call uses `respond()`, feeding in the most
          recent message received from a graph neighbor so the agent
          reacts to the discussion rather than repeating itself. Week 2's
          `respond()` already re-loads that agent's own conversation
          memory, so earlier rounds are still in context automatically.
    """

    def __init__(self, agent: Any, agent_id: str, game_id: int | None, conversation_id: str) -> None:
        self.agent = agent
        self.agent_id = agent_id
        self.game_id = game_id
        self.conversation_id = conversation_id
        self._has_spoken = False

    def speak(self, topic: str, incoming_messages: list[Message], round_number: int) -> str:
        if not self._has_spoken:
            self._has_spoken = True
            response = self.agent.generate_initial_opinion(
                topic=topic,
                conversation_id=self.conversation_id,
                game_id=self.game_id,
            )
            return response.opinion

        if incoming_messages:
            if len(incoming_messages) == 1:
                last = incoming_messages[0]
                prompt_message = (
                    f"Another analyst ({last.sender_id}) just said the following during our "
                    f"discussion:\n\n\"{last.content}\"\n\n"
                    "Considering this alongside your own evidence, do you maintain, refine, or "
                    "revise your opinion? Explain briefly."
                )
            else:
                formatted_lines = [
                    f"- Analyst '{m.sender_id}' (Round {m.round_number}): \"{m.content}\""
                    for m in incoming_messages
                ]
                context_str = "\n\n".join(formatted_lines)
                prompt_message = (
                    f"The following messages have been routed to you from other analysts during our discussion:\n\n"
                    f"{context_str}\n\n"
                    "Considering these viewpoints alongside your own evidence, do you maintain, refine, or "
                    "revise your opinion? Explain briefly."
                )
        else:
            prompt_message = "Continue the discussion, reaffirming or refining your opinion so far."

        return self.agent.respond(
            message=prompt_message,
            conversation_id=self.conversation_id,
            game_id=self.game_id,
        )


def build_week2_agents(
    topic: str,
    game_id: int | None,
    conversation_id: str,
    persona_keys: list[str] | None = None,
) -> dict[str, Week2AgentAdapter]:
    """Build real Week 2 agents (one per persona) wrapped for discussion use.

    Args:
        topic: The discussion topic (used as each agent's initial-opinion topic).
        game_id: The Week 2 match game_id (used for tool calls + memory scoping).
            May be None for personas whose tools ignore it (e.g. web_search_analyst).
        conversation_id: Shared conversation id so all agents' memories are
            scoped to the same discussion run.
        persona_keys: Which Week 2 personas to instantiate. Defaults to all
            four personas used in Week 2's main.py.

    Returns:
        Mapping of persona_id -> Week2AgentAdapter, ready to hand to
        `DiscussionOrchestrator` (its graph node ids must match these keys).
    """
    # Default persona set — callers (main.py) should always provide this via
    # match_personas_registry.resolve_personas_for_topic(). This fallback
    # is kept only as a safety net for direct / test invocations.
    persona_keys = persona_keys or [
        "tactical_analyst",
        "historical_context_analyst",
        "player_spotlight_analyst",
        "fan_narrative_analyst",
        "web_search_analyst",
    ]

    factory_module = _import_week2_module("src.agents.factory")
    memory_module = _import_week2_module("src.memory.json_memory")
    llm_module = _import_week2_module("src.llm.openrouter_client")
    registry_module = _import_week2_module("src.tools.registry")

    # Shared across all four agents for this discussion run, same as Week
    # 2's own main.py does for a single match analysis run.
    memory = memory_module.JsonMemoryStore()
    llm = llm_module.OpenRouterClient()
    tools = registry_module.ToolRegistry()

    agents: dict[str, Week2AgentAdapter] = {}
    for persona_key in persona_keys:
        persona_path = _WEEK2_PERSONAS_DIR / f"{persona_key}.yaml"
        if not persona_path.exists():
            raise FileNotFoundError(
                f"Persona file not found: {persona_path}. Confirm WEEK2_PROJECT_PATH "
                f"points at your Week 2 repo (currently resolved to: {_WEEK2_PATH})."
            )
        base_agent = factory_module.create_agent(persona_path=persona_path, memory=memory, tools=tools, llm=llm)
        agents[persona_key] = Week2AgentAdapter(
            agent=base_agent,
            agent_id=persona_key,
            game_id=game_id,
            conversation_id=conversation_id,
        )

    return agents
