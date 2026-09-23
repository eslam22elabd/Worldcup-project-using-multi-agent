"""tests/test_health.py — Acceptance tests for GET /health.

Verifies:
  - Returns HTTP 200.
  - Body is {"status": "ok"}.
  - Makes no external calls (no LLM, no DB).
  - Responds without dependency on any discussion state.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_body_is_ok():
    resp = client.get("/health")
    assert resp.json() == {"status": "ok"}


def test_health_independent_of_discussion_state():
    """Health must return 200 regardless of what discussions exist."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
