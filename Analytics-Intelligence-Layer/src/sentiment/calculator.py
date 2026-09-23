"""Sentiment scoring for discussion messages — LLM-based via OpenRouter.

Implements the Week 4 Sentiment requirements (sections 26, 28, 30, 31).

Each message's sentiment is scored by calling the OpenRouter API with
model ``openai/gpt-4o-mini``.  The LLM is asked to return a single float
in [-1.0, 1.0].  The API key is loaded from the project-local ``.env``
file (variable: OPENROUTER_API_KEY).

A missing or empty message is not treated as neutral.  In that case the
result has score=None and explains why it could not be calculated.  This
keeps "no text" separate from a real neutral score of 0.0.

If the API call fails or the response cannot be parsed as a float the
result is marked as not computable with the error as the reason.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Load from the .env file sitting next to the project root (two levels up
# from this file: src/sentiment/calculator.py → src/ → project_root/).
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)

_OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL = "openai/gpt-4o-mini"

_SYSTEM_PROMPT = (
    "You are a sentiment analysis assistant. "
    "When given a text, respond with only a single float number between "
    "-1.0 (very negative) and 1.0 (very positive) representing the overall "
    "sentiment. Do not include any explanation or extra text — only the number."
)


@dataclass
class MessageSentimentResult:
    """Sentiment result for one discussion message."""

    message_id: str
    round_number: int
    sender: str
    score: float | None
    is_computable: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "message_id": self.message_id,
            "round": self.round_number,
            "sender": self.sender,
            "score": round(self.score, 4) if self.score is not None else None,
            "is_computable": self.is_computable,
        }
        if not self.is_computable:
            result["reason"] = self.reason
        return result


def _call_openrouter(text: str) -> tuple[float | None, str]:
    """Call the OpenRouter API and return (score, reason_if_failed).

    Returns:
        (float, "") on success.
        (None, reason_string) on any failure.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return None, "OPENROUTER_API_KEY is not set in the environment or .env file."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Qubettra/Analytics-Intelligence-Layer",
    }
    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "max_tokens": 10,
        "temperature": 0,
    }

    try:
        response = requests.post(
            _OPENROUTER_API_URL, headers=headers, json=payload, timeout=30
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        return None, "OpenRouter API request timed out."
    except requests.exceptions.RequestException as exc:
        return None, f"OpenRouter API request failed: {exc}"

    try:
        content = response.json()["choices"][0]["message"]["content"].strip()
        score = float(content)
        # Clamp to [-1.0, 1.0] in case the LLM drifts slightly.
        score = max(-1.0, min(1.0, score))
        return round(score, 4), ""
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raw = response.text[:200]
        return None, f"Could not parse LLM response as float: {exc!r}. Raw: {raw!r}"


def compute_sentiment(discussion: Any) -> list[MessageSentimentResult]:
    """Calculate one sentiment result for every message in the discussion.

    Message records are read from ``discussion.rounds_data``.  Each result
    keeps the original message id, round and sender so later reporting can
    connect the score back to the discussion.
    """
    rounds_data = getattr(discussion, "rounds_data", {}) or {}
    results: list[MessageSentimentResult] = []

    for round_key, messages in rounds_data.items():
        if not isinstance(messages, list):
            continue

        try:
            default_round = int(str(round_key).split("_")[-1])
        except (TypeError, ValueError):
            default_round = 0

        for index, message in enumerate(messages):
            if not isinstance(message, dict):
                continue

            message_id = str(message.get("id") or f"{round_key}_{index}")
            sender = str(message.get("sender") or "")
            round_number = message.get("round", default_round)
            try:
                round_number = int(round_number)
            except (TypeError, ValueError):
                round_number = default_round

            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                results.append(
                    MessageSentimentResult(
                        message_id=message_id,
                        round_number=round_number,
                        sender=sender,
                        score=None,
                        is_computable=False,
                        reason="Message text is missing or empty.",
                    )
                )
                continue

            score, reason = _call_openrouter(content)
            if score is None:
                results.append(
                    MessageSentimentResult(
                        message_id=message_id,
                        round_number=round_number,
                        sender=sender,
                        score=None,
                        is_computable=False,
                        reason=reason,
                    )
                )
            else:
                results.append(
                    MessageSentimentResult(
                        message_id=message_id,
                        round_number=round_number,
                        sender=sender,
                        score=score,
                        is_computable=True,
                    )
                )

    return results
