"""tests/test_discussions.py — Acceptance tests for the discussion endpoints.

week3_client and week4_client are monkeypatched so these tests run without
any LLM calls or Week 3/4 repos on disk.

Endpoints covered:
  POST /discussions
  GET  /discussions/{id}
  GET  /discussions/{id}/analytics
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import discussions as disc_router
from backend.services.week3_client import DiscussionResult
from backend.services.week4_client import AnalyticsResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_DISCUSSION_DATA = {
    "discussion_id": "disc_abc123",
    "topic": "Argentina vs Spain — 2026 FIFA World Cup Final",
    "status": "completed",
    "participants": ["arg_esp_tactical_analyst", "arg_esp_argentina_fan"],
    "num_rounds": 3,
    "messages": [
        {
            "id": "msg_001",
            "round": 1,
            "sender": "arg_esp_tactical_analyst",
            "recipients": ["arg_esp_argentina_fan"],
            "content": "Argentina dominated the midfield.",
            "timestamp": "2026-09-20T06:00:12+00:00",
            "metadata": {},
        },
        {
            "id": "msg_002",
            "round": 1,
            "sender": "arg_esp_argentina_fan",
            "recipients": ["arg_esp_tactical_analyst"],
            "content": "Messi was unstoppable in this match.",
            "timestamp": "2026-09-20T06:00:15+00:00",
            "metadata": {},
        },
    ],
    "started_at": "2026-09-20T06:00:00+00:00",
    "completed_at": "2026-09-20T06:05:00+00:00",
    "termination_reason": "Reached configured num_rounds=3.",
}

_FAKE_ANALYTICS = AnalyticsResult(
    success=True,
    discussion_id="disc_abc123",
    opinion_change={"arg_esp_tactical_analyst": {"changes": [], "is_computable": False, "reason": "no data"}},
    agreement=[{"round_number": 1, "score": 0.75, "is_computable": True}],
    influence={"arg_esp_tactical_analyst": {"score": 0.5, "is_computable": True}},
    sentiment=[{"message_id": "msg_001", "score": 0.4, "is_computable": True}],
    stances={"arg_esp_tactical_analyst": [{"round": 1, "stance": 0.5}]},
    interaction_graph={"nodes": ["arg_esp_tactical_analyst"], "edges": {}},
)


def _make_client(monkeypatch, *, week3_result=None, load_result=None, analytics_result=None):
    if week3_result is not None:
        monkeypatch.setattr(disc_router.week3_client, "start_discussion", lambda topic: week3_result)
    if load_result is not None:
        monkeypatch.setattr(disc_router.week3_client, "load_discussion", lambda did: load_result)
    if analytics_result is not None:
        monkeypatch.setattr(disc_router.week4_client, "get_analytics", lambda did: analytics_result)

    app = FastAPI()
    app.include_router(disc_router.router)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /discussions
# ---------------------------------------------------------------------------

def test_create_discussion_returns_201(monkeypatch):
    result = DiscussionResult(
        success=True,
        discussion_id="disc_abc123",
        topic="Argentina vs Spain — 2026 FIFA World Cup Final",
        status="completed",
        agents=["arg_esp_tactical_analyst"],
        num_rounds=3,
    )
    client = _make_client(monkeypatch, week3_result=result)
    resp = client.post("/discussions", json={"topic": "Argentina Spain match"})
    assert resp.status_code == 201


def test_create_discussion_body_has_required_fields(monkeypatch):
    result = DiscussionResult(
        success=True,
        discussion_id="disc_abc123",
        topic="Argentina vs Spain — 2026 FIFA World Cup Final",
        status="completed",
        agents=["arg_esp_tactical_analyst"],
        num_rounds=3,
    )
    client = _make_client(monkeypatch, week3_result=result)
    body = client.post("/discussions", json={"topic": "Argentina Spain"}).json()
    assert "discussion_id" in body
    assert "status" in body
    assert body["discussion_id"] == "disc_abc123"


def test_create_discussion_empty_topic_returns_400(monkeypatch):
    client = _make_client(monkeypatch)
    resp = client.post("/discussions", json={"topic": "   "})
    assert resp.status_code == 400


def test_create_discussion_missing_topic_returns_422(monkeypatch):
    client = _make_client(monkeypatch)
    resp = client.post("/discussions", json={})
    assert resp.status_code == 422


def test_create_discussion_engine_failure_returns_503(monkeypatch):
    result = DiscussionResult(success=False, error="Week3 LLM unavailable")
    client = _make_client(monkeypatch, week3_result=result)
    resp = client.post("/discussions", json={"topic": "some match"})
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /discussions/{id}
# ---------------------------------------------------------------------------

def test_get_discussion_returns_200(monkeypatch):
    client = _make_client(monkeypatch, load_result=_FAKE_DISCUSSION_DATA)
    resp = client.get("/discussions/disc_abc123")
    assert resp.status_code == 200


def test_get_discussion_body_shape(monkeypatch):
    client = _make_client(monkeypatch, load_result=_FAKE_DISCUSSION_DATA)
    body = client.get("/discussions/disc_abc123").json()
    assert body["discussion_id"] == "disc_abc123"
    assert "rounds" in body
    assert isinstance(body["rounds"], list)
    # round 1 has 2 messages
    assert len(body["rounds"][0]["messages"]) == 2


def test_get_discussion_not_found_returns_404(monkeypatch):
    client = _make_client(monkeypatch, load_result=None)
    resp = client.get("/discussions/nonexistent_id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /discussions/{id}/analytics
# ---------------------------------------------------------------------------

def test_get_analytics_returns_200(monkeypatch):
    client = _make_client(monkeypatch, analytics_result=_FAKE_ANALYTICS)
    resp = client.get("/discussions/disc_abc123/analytics")
    assert resp.status_code == 200


def test_get_analytics_body_has_all_keys(monkeypatch):
    client = _make_client(monkeypatch, analytics_result=_FAKE_ANALYTICS)
    body = client.get("/discussions/disc_abc123/analytics").json()
    for key in ("discussion_id", "opinion_change", "agreement", "influence", "sentiment", "stances", "interaction_graph"):
        assert key in body, f"Missing key: {key}"


def test_get_analytics_not_found_returns_404(monkeypatch):
    result = AnalyticsResult(
        success=False,
        discussion_id="bad_id",
        error="Analytics export not found for discussion 'bad_id'.",
    )
    client = _make_client(monkeypatch, analytics_result=result)
    resp = client.get("/discussions/bad_id/analytics")
    assert resp.status_code == 404


def test_get_analytics_engine_failure_returns_503(monkeypatch):
    result = AnalyticsResult(
        success=False,
        discussion_id="disc_abc123",
        error="OpenRouter API rate limit exceeded.",
    )
    client = _make_client(monkeypatch, analytics_result=result)
    resp = client.get("/discussions/disc_abc123/analytics")
    assert resp.status_code == 503
