"""Retrieval router — README section 24 (Integration With Week 1).

Ownership boundary (per the team split): this file, and everything under
`backend/integrations/week1_retrieval/`, is the ONLY place Week 1's
retrieval system is touched. `backend/main.py` and the rest of the
backend (topics, discussions, analytics, health) never import Week 1
code directly -- they only ever see this router's HTTP contract
(`schemas/retrieval.py`). This means the Week 1 integration can be
changed, reimplemented, or even swapped for a different retrieval
backend later without anyone else's code changing.

Where this fits in the app (per section 24, "the exact way this appears
in the UI is your choice"): exposed here as a standalone endpoint the
frontend's Discussion/Topic views can call directly (e.g. to let a user
search the knowledge base before starting a discussion), independent of
whether any given discussion's agents also call retrieval internally via
Week 2/3.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.integrations.week1_retrieval.client import search_knowledge_base
from backend.schemas.retrieval import RetrievalRequest, RetrievalResponse, RetrievalSource

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse)
def search(request: RetrievalRequest) -> RetrievalResponse:
    """Search the Week 1 knowledge base.

    Request body:
        {"query": "Tiki-taka tactical style", "top_k": 3}

    Response (success):
        {
            "query": "Tiki-taka tactical style",
            "success": true,
            "result_count": 3,
            "sources": [
                {"title": "Tiki-taka", "url": "https://...", "category": "tactical_concept", "similarity": 0.77}
            ],
            "error": null
        }

    Response (failure -- Week 1 unreachable, or nothing relevant found):
        {"query": "...", "success": false, "result_count": 0, "sources": [], "error": "..."}

    This endpoint never raises an HTTP error for a retrieval failure --
    "nothing found" or "Week 1 unreachable" are valid, expected outcomes
    the frontend should handle gracefully (see README section 28: Error
    Handling), not exceptional server errors.
    """
    result = search_knowledge_base(query=request.query, top_k=request.top_k)

    return RetrievalResponse(
        query=request.query,
        success=result.success,
        result_count=len(result.sources),
        sources=[RetrievalSource(**s) for s in result.sources],
        error=result.error,
    )
