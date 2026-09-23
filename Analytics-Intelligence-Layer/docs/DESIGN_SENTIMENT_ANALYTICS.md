# Design Decisions — Sentiment & Unified Analytics

This document covers the Week 4 scope for Part 3: Sentiment and the
Unified Analytics Engine (sections 17-19 and the sentiment/missing-data
requirements in sections 28 and 36).

## 1. Sentiment

### Metric Documentation (section 36 template)

Metric: Message Sentiment Score

Purpose:
Give every discussion message a comparable sentiment signal so the tone 
of the discussion can be inspected and analyzed over time.

Input:
Message text from Week 3 `rounds` data.

Method:
Uses an LLM (Language Model) via the OpenRouter API (specifically `openai/gpt-4o-mini`).
The LLM is prompted to evaluate the sentiment of the message and return a single 
floating-point number representing the sentiment score.

Output:
One result per message.

Range:
[-1.0, 1.0]

Interpretation:
+1.0 = highly positive sentiment.
 0.0 = neutral sentiment.
-1.0 = highly negative sentiment.

Limitations:
- Requires an active internet connection and a valid OpenRouter API key.
- API latency: processing large discussions sequentially can take time.
- Subjective variation: the LLM may slightly adjust its scoring for similar text.

### Missing data or API failures

Missing or empty message text is not converted to `0.0`.
Likewise, if the OpenRouter API fails, times out, or returns an unparseable response,
it is handled gracefully without crashing.

Instead, the result uses:

- `score=None`
- `is_computable=False`
- a `reason` explaining that the message text is missing, or the API call failed (and why).

A real message with text but evaluated as neutral by the LLM will 
receive a valid computable score of `0.0`.

## 2. Unified Analytics Engine

`src/analytics/engine.py` provides a single entry point for running the
Week 4 analytics.

The main function is:

`run_analytics(discussion)`

It accepts either:

- a loaded `LoadedDiscussion` object
- a path to a saved Week 3 discussion export

The engine builds the shared stance series once and then calls the
existing analytics modules:

- `compute_opinion_change()`
- `compute_agreement()`
- `compute_influence()`
- `compute_sentiment()`

The existing Opinion Change, Agreement, and Influence implementations
are reused instead of being copied into the unified engine.

### Unified output

The engine returns one `AnalyticsResult` containing:

Analytics Result
├── discussion_id
├── opinion_change
├── agreement
├── influence
└── sentiment

The result also provides `to_dict()` so the analytics can be easily
passed to reporting or frontend code later.

This gives Part 4 one object to consume instead of requiring it to know
where each individual metric is implemented.

## 3. Reporting and Visualization (Part 4)

Automatic report generation and visualizations (Opinion Trajectory and Interaction Graph) 
are handled via the `src/reporting/` package. The reports are saved automatically as 
Markdown and PNG files in the `reports/` and `outputs/` directories when running `main.py`.

## 4. Design Choice

The sentiment implementation uses an external LLM via OpenRouter. 

This was chosen over a fixed lexical heuristic to allow for deep semantic 
understanding of football discussions, sarcastic remarks, and contextual tone, 
providing much higher quality analytics than simple keyword matching.

The unified engine keeps the analytics components separate. Each
metric remains implemented in its own module, while
`run_analytics()` provides one interface for using all of them together.

This makes the system easier to test and allows individual metrics to be
improved later without changing the interface used by the reporting layer.

## 5. Week 5 Handoff

The unified `AnalyticsResult` is the main output provided to the next
stage of the project.

Part 4 can use:

`run_analytics(discussion)`

and then access:

- opinion change
- agreement
- influence
- sentiment

