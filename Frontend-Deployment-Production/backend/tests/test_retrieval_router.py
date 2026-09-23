"""Tests for the retrieval router — the only backend piece this person owns.

These don't require a real Week 1/2 checkout: search_knowledge_base is
monkeypatched so the router's own logic (status codes, schema shape,
graceful error passthrough) is what's actually being tested.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.integrations.week1_retrieval.client import KnowledgeSearchResult
from backend.routers import retrieval as retrieval_router


def _make_client(monkeypatch, fake_result: KnowledgeSearchResult):
    monkeypatch.setattr(
        retrieval_router, "search_knowledge_base", lambda query, top_k: fake_result
    )
    app = FastAPI()
    app.include_router(retrieval_router.router)
    return TestClient(app)


def test_successful_search_returns_sources(monkeypatch):
    fake = KnowledgeSearchResult(
        success=True,
        sources=[{"title": "Tiki-taka", "url": "https://en.wikipedia.org/wiki/Tiki-taka", "category": "tactical_concept", "similarity": 0.77}],
    )
    client = _make_client(monkeypatch, fake)

    resp = client.post("/retrieval/search", json={"query": "Tiki-taka", "top_k": 3})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["result_count"] == 1
    assert body["sources"][0]["title"] == "Tiki-taka"
    assert body["error"] is None


def test_failed_search_returns_200_with_error_not_a_500(monkeypatch):
    fake = KnowledgeSearchResult(success=False, sources=[], error="Postgres unreachable")
    client = _make_client(monkeypatch, fake)

    resp = client.post("/retrieval/search", json={"query": "anything", "top_k": 3})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["result_count"] == 0
    assert body["error"] == "Postgres unreachable"


def test_missing_query_is_rejected_by_validation(monkeypatch):
    fake = KnowledgeSearchResult(success=True, sources=[])
    client = _make_client(monkeypatch, fake)

    resp = client.post("/retrieval/search", json={"top_k": 3})  # no "query"
    assert resp.status_code == 422


def test_default_top_k_is_applied(monkeypatch):
    captured = {}

    def fake_search(query, top_k):
        captured["top_k"] = top_k
        return KnowledgeSearchResult(success=True, sources=[])

    monkeypatch.setattr(retrieval_router, "search_knowledge_base", fake_search)
    app = FastAPI()
    app.include_router(retrieval_router.router)
    client = TestClient(app)

    client.post("/retrieval/search", json={"query": "test"})
    assert captured["top_k"] == 3
