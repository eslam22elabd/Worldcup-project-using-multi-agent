"""tests/test_topics.py — Acceptance tests for GET /topics.

The Week 3 registry import is monkeypatched so these tests run without
needing the Week 3 repo on disk.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import topics as topics_router


def _make_client(monkeypatch, fake_topics: list[str]):
    """Build a test client with the registry import replaced."""
    monkeypatch.setattr(
        topics_router,
        "_get_topics_from_registry",
        lambda: fake_topics,
    )
    app = FastAPI()
    app.include_router(topics_router.router)
    return TestClient(app)


def test_topics_returns_200(monkeypatch):
    client = _make_client(
        monkeypatch,
        ["Argentina vs Spain — 2026 Final", "France vs England — Third Place"],
    )
    resp = client.get("/topics")
    assert resp.status_code == 200


def test_topics_body_has_topics_key(monkeypatch):
    fake = ["Argentina vs Spain — 2026 Final"]
    client = _make_client(monkeypatch, fake)
    body = client.get("/topics").json()
    assert "topics" in body
    assert body["topics"] == fake


def test_topics_returns_503_on_import_error(monkeypatch):
    def _fail():
        raise ImportError("Week 3 not installed")

    monkeypatch.setattr(topics_router, "_get_topics_from_registry", _fail)
    app = FastAPI()
    app.include_router(topics_router.router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/topics")
    assert resp.status_code == 503
