"""Sentiment tests — Week 4 sections 26, 28, 30, 31.

Covers:
    - Positive, negative and neutral message scores (mocked LLM).
    - Missing message text is handled explicitly.
    - Every valid message receives a sentiment result.
    - API key missing returns not-computable result.
    - API failure returns not-computable result.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.ingestion.discussion_loader import LoadedDiscussion, ValidationReport
from src.sentiment.calculator import compute_sentiment


def _discussion(rounds: dict) -> LoadedDiscussion:
    return LoadedDiscussion(
        discussion_id="disc_test",
        topic="test",
        participants=["agent_a", "agent_b"],
        num_rounds=1,
        snapshots=[],
        report=ValidationReport(),
        rounds_data=rounds,
    )


def _mock_response(score_text: str) -> MagicMock:
    """Build a fake requests.Response that returns score_text as the LLM reply."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": score_text}}]
    }
    mock_resp.raise_for_status.return_value = None
    return mock_resp


@patch("src.sentiment.calculator.requests.post")
@patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"})
def test_positive_message_gets_positive_score(mock_post):
    mock_post.return_value = _mock_response("0.85")
    results = compute_sentiment(_discussion({"round_1": [
        {"id": "msg_1", "round": 1, "sender": "agent_a", "content": "A great and successful victory."}
    ]}))
    assert results[0].score > 0
    assert results[0].is_computable


@patch("src.sentiment.calculator.requests.post")
@patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"})
def test_negative_message_gets_negative_score(mock_post):
    mock_post.return_value = _mock_response("-0.75")
    results = compute_sentiment(_discussion({"round_1": [
        {"id": "msg_1", "round": 1, "sender": "agent_a", "content": "A difficult loss and disappointing result."}
    ]}))
    assert results[0].score < 0


@patch("src.sentiment.calculator.requests.post")
@patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"})
def test_neutral_message_can_have_zero_score(mock_post):
    mock_post.return_value = _mock_response("0.0")
    results = compute_sentiment(_discussion({"round_1": [
        {"id": "msg_1", "round": 1, "sender": "agent_a", "content": "The match started in the first half."}
    ]}))
    assert results[0].score == 0.0
    assert results[0].is_computable


def test_missing_message_text_is_not_called_neutral():
    """No API call should happen for empty content — handled before calling LLM."""
    results = compute_sentiment(_discussion({"round_1": [
        {"id": "msg_1", "round": 1, "sender": "agent_a", "content": ""}
    ]}))
    assert results[0].score is None
    assert not results[0].is_computable
    assert "missing or empty" in results[0].reason


@patch.dict("os.environ", {"OPENROUTER_API_KEY": ""})
def test_missing_api_key_returns_not_computable():
    results = compute_sentiment(_discussion({"round_1": [
        {"id": "msg_1", "round": 1, "sender": "agent_a", "content": "Some content."}
    ]}))
    assert results[0].score is None
    assert not results[0].is_computable
    assert "OPENROUTER_API_KEY" in results[0].reason


@patch("src.sentiment.calculator.requests.post")
@patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"})
def test_api_failure_returns_not_computable(mock_post):
    import requests as req_lib
    mock_post.side_effect = req_lib.exceptions.RequestException("connection refused")
    results = compute_sentiment(_discussion({"round_1": [
        {"id": "msg_1", "round": 1, "sender": "agent_a", "content": "Some content."}
    ]}))
    assert results[0].score is None
    assert not results[0].is_computable
    assert "failed" in results[0].reason.lower()


@patch("src.sentiment.calculator.requests.post")
@patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"})
def test_every_message_gets_a_result(mock_post):
    mock_post.side_effect = [
        _mock_response("0.8"),
        _mock_response("-0.5"),
        _mock_response("0.1"),
    ]
    results = compute_sentiment(_discussion({
        "round_1": [
            {"id": "msg_1", "round": 1, "sender": "agent_a", "content": "Good performance."},
            {"id": "msg_2", "round": 1, "sender": "agent_b", "content": "Bad performance."},
        ],
        "round_2": [
            {"id": "msg_3", "round": 2, "sender": "agent_a", "content": "No major change."},
        ],
    }))
    assert len(results) == 3
    assert {result.message_id for result in results} == {"msg_1", "msg_2", "msg_3"}
