from __future__ import annotations

from typing import Any, Protocol

from src.memory.base import MemoryStore
from src.models.persona import Persona
from src.models.responses import AgentResponse, ToolResult


class ToolRegistryProtocol(Protocol):
    def execute(self, tool_name: str, **kwargs: Any) -> ToolResult:
        ...


class LLMClientProtocol(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class BaseAgent:
    """Reusable agent abstraction shared by all persona configurations.

    Tools and the LLM provider are injected dependencies. This lets the core
    work before the team chooses OpenRouter, Claude, Gemini, or another LLM,
    and before retrieval's internal implementation is final.
    """

    def __init__(self, persona: Persona, memory: MemoryStore, tools: ToolRegistryProtocol, llm: LLMClientProtocol) -> None:
        self.persona = persona
        self.memory = memory
        self.tools = tools
        self.llm = llm

    def build_session_id(self, conversation_id: str, game_id: int | None = None) -> str:
        scope = str(game_id) if game_id is not None else "general"
        return f"{self.persona.id}__{scope}__{conversation_id}"

    def _tool_arguments(self, topic: str, game_id: int | None, top_k: int) -> dict[str, Any]:
        if self.persona.input_mode == "match_specific":
            if game_id is None:
                raise ValueError(
                    f"Persona '{self.persona.id}' requires game_id for tool '{self.persona.required_tool}'."
                )
            return {"game_id": game_id}
        if self.persona.input_mode == "search_query":
            # web_search tool only accepts `query`, not `top_k`
            return {"query": topic}
        return {"query": topic, "top_k": top_k}

    @staticmethod
    def _format_memory(messages: list[dict[str, Any]]) -> str:
        if not messages:
            return "No previous interaction is stored for this session."
        return "\n".join(f"{item['role'].upper()}: {item['content']}" for item in messages)

    @staticmethod
    def _format_evidence(data: Any) -> str:
        return data if isinstance(data, str) else str(data)

    def build_prompt(self, topic: str, memory_messages: list[dict[str, Any]], evidence: Any) -> str:
        return f"""You are a configurable football-intelligence agent.

PERSONA
{self.persona.as_prompt_text()}

TASK
Provide an initial opinion about this topic:
{topic}

CONVERSATION MEMORY
{self._format_memory(memory_messages)}

AVAILABLE EVIDENCE
{self._format_evidence(evidence)}

RESPONSE RULES
1. Use supplied evidence as the basis for factual claims.
2. Follow the persona's expertise, priorities, stance, and communication style.
3. Do not invent match events, statistics, rules, or sources.
4. Clearly distinguish observed evidence from interpretation.
5. State uncertainty if evidence is incomplete or conflicting.
6. Produce a focused initial opinion, not a final absolute judgment.
"""

    def generate_initial_opinion(self, topic: str, conversation_id: str = "default", game_id: int | None = None, top_k: int = 3) -> AgentResponse:
        session_id = self.build_session_id(conversation_id=conversation_id, game_id=game_id)
        previous_memory = self.memory.get_recent(session_id=session_id, limit=10)

        self.memory.add(
            session_id=session_id,
            role="user",
            content=topic,
            metadata={"game_id": game_id, "persona_id": self.persona.id},
        )

        arguments = self._tool_arguments(topic=topic, game_id=game_id, top_k=top_k)
        tool_result = self.tools.execute(self.persona.required_tool, **arguments)

        if not tool_result.success:
            error_message = f"I could not obtain evidence from '{self.persona.required_tool}'. Reason: {tool_result.error or 'unknown tool error'}"
            self.memory.add(session_id=session_id, role="assistant", content=error_message)
            return AgentResponse(
                agent_id=self.persona.id,
                persona_name=self.persona.name,
                topic=topic,
                opinion=error_message,
                evidence=None,
                sources=[],
                tool_calls=[{"tool_name": tool_result.tool_name, "arguments": arguments, "success": False}],
                memory_used=bool(previous_memory),
                session_id=session_id,
            )

        prompt = self.build_prompt(topic=topic, memory_messages=previous_memory, evidence=tool_result.data)
        opinion = self.llm.generate(prompt)
        sources = tool_result.metadata.get("sources", [])

        self.memory.add(
            session_id=session_id,
            role="tool",
            content=self._format_evidence(tool_result.data),
            metadata={"tool_name": tool_result.tool_name, **tool_result.metadata},
        )
        self.memory.add(session_id=session_id, role="assistant", content=opinion, metadata={"sources": sources})

        return AgentResponse(
            agent_id=self.persona.id,
            persona_name=self.persona.name,
            topic=topic,
            opinion=opinion,
            evidence=tool_result.data,
            sources=sources,
            tool_calls=[{"tool_name": tool_result.tool_name, "arguments": arguments, "success": True}],
            memory_used=bool(previous_memory),
            session_id=session_id,
        )

    def respond(self, message: str, conversation_id: str = "default", game_id: int | None = None) -> str:
        """Follow-up interaction used to demonstrate persistent memory."""
        session_id = self.build_session_id(conversation_id=conversation_id, game_id=game_id)
        history = self.memory.get_recent(session_id=session_id, limit=10)
        self.memory.add(session_id=session_id, role="user", content=message)

        prompt = f"""You are a configurable football-intelligence agent.

PERSONA
{self.persona.as_prompt_text()}

CONVERSATION MEMORY
{self._format_memory(history)}

NEW USER MESSAGE
{message}

Respond consistently with the stored memory. If asked about an earlier message,
use stored conversation context. Do not invent factual match data.
"""
        reply = self.llm.generate(prompt)
        self.memory.add(session_id=session_id, role="assistant", content=reply)
        return reply
