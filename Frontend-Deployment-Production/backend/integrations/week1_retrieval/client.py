"""Week 1 retrieval client.

This module (and its own sub-package) is the sole owner of everything
related to reaching the Week 1 knowledge base. It reuses Week 2's
already-working `get_knowledge` tool (see Week 2's
`src/tools/knowledge_retrieval_tool.py`) rather than talking to Week 1's
Postgres/embeddings directly a second time, and applies the same
sys.modules-swap fix used throughout Weeks 2-4 to work around Week 1/2/3
all naming their top-level package `src`.

Nothing outside this sub-package should import from here except
`backend/routers/retrieval.py`.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Same sibling-repo assumption as Week 2/3/4: this backend sits inside
# the shared `projects/` (or repo-root) folder alongside Week 2's repo.
# Override with WEEK2_PROJECT_PATH if your layout differs.
_DEFAULT_WEEK2_PATH = Path(__file__).resolve().parents[4] / "Intelligent-Agent-Framework-week2"
_WEEK2_PATH = Path(os.getenv("WEEK2_PROJECT_PATH", str(_DEFAULT_WEEK2_PATH))).resolve()


@dataclass
class KnowledgeSearchResult:
    success: bool
    sources: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def _import_week2_get_knowledge():
    """Import Week 2's get_knowledge, working around the shared `src` package name."""
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
        module = importlib.import_module("src.tools.knowledge_retrieval_tool")
        get_knowledge = module.get_knowledge
    finally:
        for name in list(sys.modules):
            if name == "src" or name.startswith("src."):
                del sys.modules[name]
        sys.modules.update(saved_modules)

    return get_knowledge


def search_knowledge_base(query: str, top_k: int = 3) -> KnowledgeSearchResult:
    """Search the Week 1 knowledge base via Week 2's get_knowledge tool.

    Returns a KnowledgeSearchResult -- never raises for an ordinary
    "not found" or "Week 1 unreachable" outcome, since those are expected
    conditions the caller (the /retrieval/search route) turns into a
    normal (success=False) HTTP response rather than a server error.
    """
    try:
        get_knowledge = _import_week2_get_knowledge()
    except ImportError as exc:
        return KnowledgeSearchResult(
            success=False,
            error=f"Could not reach the Week 1/2 retrieval system: {exc}",
        )

    tool_result = get_knowledge(query=query, top_k=top_k)

    if not tool_result.success:
        return KnowledgeSearchResult(success=False, error=tool_result.error)

    raw_chunks = (tool_result.metadata or {}).get("raw_chunks", [])
    sources = [
        {
            "title": chunk.get("title", ""),
            "url": chunk.get("url", ""),
            "category": chunk.get("category", ""),
            "similarity": float(chunk.get("similarity", 0.0)),
        }
        for chunk in raw_chunks
    ]
    return KnowledgeSearchResult(success=True, sources=sources)
