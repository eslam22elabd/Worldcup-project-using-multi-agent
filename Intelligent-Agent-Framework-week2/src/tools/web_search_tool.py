"""Tool: web_search

Performs a real-time internet search via the Tavily Search API and returns
a formatted summary of the most relevant results.
"""

from __future__ import annotations

import os
from typing import Any

from src.models.responses import ToolResult


def web_search(query: str, max_results: int = 3) -> ToolResult:
    """Search the internet for the given query using Tavily.

    Args:
        query: Natural-language search query (e.g. "Mexico vs South Africa 2026 World Cup").
        max_results: Maximum number of search results to include.

    Returns:
        ToolResult with formatted search results on success, error on failure.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return ToolResult(
            success=False,
            tool_name="web_search",
            error=(
                "TAVILY_API_KEY is not set. "
                "Add it to your .env file to enable internet search."
            ),
        )

    try:
        from tavily import TavilyClient  # type: ignore
    except ImportError:
        return ToolResult(
            success=False,
            tool_name="web_search",
            error="tavily-python is not installed. Run: pip install tavily-python",
        )

    try:
        client = TavilyClient(api_key=api_key)
        response: dict[str, Any] = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            success=False,
            tool_name="web_search",
            error=f"Tavily search failed: {exc}",
        )

    results: list[dict[str, Any]] = response.get("results", [])
    answer: str = response.get("answer", "")

    if not results and not answer:
        return ToolResult(
            success=False,
            tool_name="web_search",
            error=f"No results returned for query: '{query}'",
        )

    # Format the results into a readable block for the LLM
    parts: list[str] = []

    if answer:
        parts.append(f"[TAVILY ANSWER]\n{answer}")

    for i, result in enumerate(results, start=1):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        content = result.get("content", "").strip()
        parts.append(f"[SOURCE {i}] {title}\nURL: {url}\n{content}")

    formatted = "\n\n".join(parts)

    sources = [
        {"title": r.get("title", ""), "url": r.get("url", "")}
        for r in results
    ]

    return ToolResult(
        success=True,
        tool_name="web_search",
        data=formatted,
        metadata={"query": query, "result_count": len(results), "sources": sources},
    )
