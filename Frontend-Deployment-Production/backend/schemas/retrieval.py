"""Request/response contracts for the retrieval endpoint.

README section 22 requires documenting the request/response format of
every public endpoint. This module IS that documentation -- the Pydantic
models double as the OpenAPI schema FastAPI generates automatically at
/docs, so this file is the single source of truth for the contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievalSource(BaseModel):
    """One evidence source returned by the Week 1 knowledge base."""

    title: str = Field(..., description="Title of the retrieved document/chunk.")
    url: str = Field("", description="Source URL, if available.")
    category: str = Field("", description="Week 1 category, e.g. 'tactical_concept'.")
    similarity: float = Field(..., description="Similarity score in [0, 1]; higher is more relevant.")


class RetrievalRequest(BaseModel):
    """Body for POST /retrieval/search."""

    query: str = Field(..., min_length=1, description="Natural-language question or topic to search for.")
    top_k: int = Field(3, ge=1, le=10, description="Number of ranked results to return.")


class RetrievalResponse(BaseModel):
    """Response for POST /retrieval/search."""

    query: str
    success: bool = Field(..., description="False if the Week 1 system could not be reached or found nothing.")
    result_count: int
    sources: list[RetrievalSource]
    error: str | None = Field(None, description="Present only when success is False.")
