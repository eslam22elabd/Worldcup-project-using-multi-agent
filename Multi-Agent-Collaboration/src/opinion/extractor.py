"""Opinion stance extractor — LLM-as-Judge implementation.

Replaces the old keyword-based heuristic with a real LLM call so that
`polarity` reflects the agent's actual stance on the topic, not a
bag-of-words score.

Design decisions:
    - Only `polarity` is extracted (range -1.0 to +1.0).
    - `confidence`, `agreement_score`, and `key_arguments` have been removed.
    - Full discussion context (all previous messages) is passed to the judge
      so it can resolve relative statements like "I agree with the analyst".
    - On LLM failure the request is retried after `retry_delay_seconds`
      (default 15 s). No heuristic fallback.
    - Uses the same OpenRouter client as Week 2 agents.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from src.opinion.models import Stance


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM_PROMPT = """\
You are an expert discussion analyst. Your only job is to estimate the \
polarity of an agent's opinion about the given topic.

Polarity rules:
  +1.0  = extremely positive / strongly favours one side
   0.0  = neutral / balanced / no clear stance
  -1.0  = extremely negative / strongly opposes or criticises

Return ONLY a valid JSON object with a single key, no explanation, no markdown:
{"polarity": <float between -1.0 and 1.0>}
"""

_JUDGE_USER_TEMPLATE = """\
DISCUSSION TOPIC: {topic}

DISCUSSION HISTORY SO FAR (ordered, oldest first):
{history}

NOW JUDGE THIS AGENT'S RESPONSE:
Agent ID  : {agent_id}
Round     : {round_number}
Response  : {opinion_text}

Return ONLY: {{"polarity": <float>}}
"""


def _build_history_str(context_messages: list[dict[str, Any]]) -> str:
    """Format prior messages into a compact history string for the judge."""
    if not context_messages:
        return "(no prior messages — this is the first opinion)"
    lines = []
    for msg in context_messages:
        sender = msg.get("sender_id", msg.get("sender", "unknown"))
        rnd = msg.get("round_number", msg.get("round", "?"))
        content = str(msg.get("content", ""))[:600]  # trim very long messages
        lines.append(f"[Round {rnd} | {sender}]: {content}")
    return "\n\n".join(lines)


def _parse_polarity(raw: str) -> float | None:
    """Extract polarity float from LLM JSON response. Returns None on failure."""
    raw = raw.strip()
    try:
        data = json.loads(raw)
        val = data.get("polarity")
        if val is not None:
            return max(-1.0, min(1.0, float(val)))
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Regex fallback: scan for the number after "polarity"
    match = re.search(r'"polarity"\s*:\s*(-?\d+(?:\.\d+)?)', raw)
    if match:
        try:
            return max(-1.0, min(1.0, float(match.group(1))))
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# LLM client loader (lazy, cached at module level)
# ---------------------------------------------------------------------------

_llm_client_cache: Any = None


def _get_llm_client() -> Any:
    """Return a cached OpenRouterClient loaded from the Week 2 sibling repo."""
    global _llm_client_cache
    if _llm_client_cache is not None:
        return _llm_client_cache

    try:
        from src.adapters.week2_agent_adapter import _import_week2_module
        llm_module = _import_week2_module("src.llm.openrouter_client")
        _llm_client_cache = llm_module.OpenRouterClient()
    except Exception as exc:
        raise RuntimeError(
            "LLMJudgeExtractor: could not load OpenRouterClient from Week 2 repo. "
            f"Make sure WEEK2_PROJECT_PATH is set correctly. Error: {exc}"
        ) from exc

    return _llm_client_cache


# ---------------------------------------------------------------------------
# Public extractor
# ---------------------------------------------------------------------------


class LLMJudgeExtractor:
    """Extracts opinion polarity using an LLM judge with full discussion context.

    Args:
        max_retries: How many times to attempt the LLM call before giving up.
        retry_delay_seconds: Seconds to wait between attempts (default 15).
        model: OpenRouter model override. None = use client default (same
               model as Week 2 agents).
    """

    def __init__(
        self,
        max_retries: int = 5,
        retry_delay_seconds: float = 15.0,
        model: str | None = None,
    ) -> None:
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.model = model

    def extract(
        self,
        opinion_text: str,
        agent_id: str,
        round_number: int,
        topic: str,
        context_messages: list[dict[str, Any]] | None = None,
    ) -> Stance:
        """Call the LLM judge and return a Stance with the extracted polarity.

        Retries up to `max_retries` times with a `retry_delay_seconds` pause.
        Never falls back to heuristics.

        Args:
            opinion_text: The full text produced by the agent this round.
            agent_id: ID of the agent being judged.
            round_number: Current round number.
            topic: The discussion topic.
            context_messages: Prior message dicts with keys:
                sender_id/sender, round_number/round, content.

        Returns:
            Stance with polarity set by the LLM judge.

        Raises:
            RuntimeError: If all retry attempts are exhausted.
        """
        user_prompt = _JUDGE_USER_TEMPLATE.format(
            topic=topic,
            history=_build_history_str(context_messages or []),
            agent_id=agent_id,
            round_number=round_number,
            opinion_text=opinion_text,
        )

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                polarity = self._call_llm(user_prompt)
                print(
                    f"  [LLM Judge] {agent_id} | round {round_number} "
                    f"-> polarity={polarity:+.3f}"
                )
                return Stance(polarity=polarity)

            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    print(
                        f"  [LLM Judge] attempt {attempt}/{self.max_retries} failed "
                        f"({exc}). Retrying in {self.retry_delay_seconds}s ..."
                    )
                    time.sleep(self.retry_delay_seconds)
                else:
                    print(
                        f"  [LLM Judge] all {self.max_retries} attempts failed "
                        f"for {agent_id} round {round_number}."
                    )

        raise RuntimeError(
            f"LLMJudgeExtractor exhausted {self.max_retries} retries for "
            f"agent '{agent_id}' round {round_number}. Last error: {last_error}"
        ) from last_error

    def _call_llm(self, user_prompt: str) -> float:
        """Make the actual LLM API call and return the parsed polarity float."""
        llm = _get_llm_client()

        messages = [
            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Use the underlying OpenAI client to support messages list and overrides
        try:
            completion = llm._client.chat.completions.create(
                model=self.model or llm.model,
                temperature=llm.temperature,
                max_tokens=llm.max_tokens,
                messages=messages,
            )
            raw_response = completion.choices[0].message.content.strip()
        except Exception as exc:
            raise RuntimeError(f"LLM call failed: {exc}") from exc

        polarity = _parse_polarity(raw_response)
        if polarity is None:
            raise ValueError(
                f"Could not parse polarity from LLM response: {raw_response!r}"
            )

        return polarity
