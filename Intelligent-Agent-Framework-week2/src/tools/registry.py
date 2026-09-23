"""ToolRegistry — dispatches tool calls to concrete implementations.

Implements the ToolRegistryProtocol expected by BaseAgent, so no agent code
needs to change when a new tool is added — just register it here.
"""

from __future__ import annotations

from typing import Any, Callable

from src.models.responses import ToolResult
from src.tools.match_summary_tool import get_match_summary
from src.tools.match_opinion_tool import get_match_opinions
from src.tools.web_search_tool import web_search


class ToolRegistry:
    """Central registry that maps tool names to their callable implementations.

    Usage::

        registry = ToolRegistry()
        result = registry.execute("get_match_summary", game_id=1953853)
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., ToolResult]] = {
            "get_match_summary": get_match_summary,
            "get_match_opinions": get_match_opinions,
            "web_search": web_search,
        }

    def register(self, name: str, fn: Callable[..., ToolResult]) -> None:
        """Register an additional tool at runtime."""
        self._tools[name] = fn

    def available_tools(self) -> list[str]:
        """Return the names of all currently registered tools."""
        return list(self._tools.keys())

    def execute(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a registered tool by name.

        Args:
            tool_name: The registered name of the tool to call.
            **kwargs: Arguments forwarded verbatim to the tool function.

        Returns:
            ToolResult from the tool, or an error ToolResult if the tool is
            not registered.
        """
        fn = self._tools.get(tool_name)
        if fn is None:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=(
                    f"Tool '{tool_name}' is not registered. "
                    f"Available tools: {self.available_tools()}"
                ),
            )
        try:
            return fn(**kwargs)
        except Exception as exc:  
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' raised an unexpected error: {exc}",
            )
