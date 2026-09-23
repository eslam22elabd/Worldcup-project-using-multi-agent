# Design Decisions — Sections 4, 6, 7, 8, 27, 28

This document covers only the scope tackled in this pass: consuming
Week 3's discussion output and computing Opinion Change. Agreement/
Disagreement, Influence, Sentiment, the unified analytics interface,
report generation, and visualizations (sections 5, 9-26) are
deliberately out of scope here.

## 1. Input (section 4)

`src/ingestion/discussion_loader.py` reads a Week 3 `week4_*.json`
export directly (the `schema_version: "week4.v1"` payload Week 3's
`DiscussionStore.export_for_week4()` already produces). No part of the
discussion is recreated or re-run — only `participants`, `num_rounds`,
and `opinion_history` are read, since those are the only fields Opinion
Change analytics need.

## 2. Representing opinions numerically (section 7)

**Decision: reuse Week 3's own `stance.polarity` value as-is, rather
than computing a new stance score from the opinion text.**

Week 3 already derives a numeric polarity (range `[-1.0, 1.0]`) for
every opinion snapshot via a lexical heuristic (positive/negative word
counts — see Week 3's `src/opinion/extractor.py`). Recomputing a second,
independent stance score from the same opinion text here would violate
section 4's explicit instruction not to recreate what Week 3 already
produced, and would risk two disagreeing numbers for the same opinion
with no principled way to reconcile them.

Documented per section 7's checklist:
- **What it represents**: how favorably or critically an opinion's
  language leaned, per Week 3's lexical heuristic.
- **Range**: `[-1.0, 1.0]`. Out-of-range values in the source data are
  clamped during validation (with a warning), not silently accepted or
  rejected outright.
- **Higher value**: more positive/favorable framing. **Lower value**:
  more critical/negative framing. **Near zero**: neutral language *or*
  no strong lexical signal — these two cases are indistinguishable from
  the number alone, which is a real limitation of a lexical heuristic,
  stated here rather than hidden.
- **Conversion**: none performed in this repo — taken directly from
  `opinion_history[agent_id][i].stance.polarity`.
- **Cross-round interpretation**: treated as a *relative* signal for a
  single agent's own trajectory. Comparing polarity *between different
  agents* is weaker evidence than comparing one agent *across its own
  rounds*, since the heuristic has no notion of the specific claim being
  debated — only word-level sentiment.

## 3. Stance series (section 6)

`src/opinion_change/stance_series.py` builds one `AgentStanceSeries` per
participant: a list of `(round_number, stance)` points, sorted by round.
Every participant gets an entry even with zero data points
(`has_data == False`), so "no data yet" is explicit and inspectable
rather than the agent silently disappearing from the result.

Missing rounds are simply absent from `points` — a missing round is
**not** filled with `0.0` or any placeholder, since `0.0` is also a
legitimate stance value; inventing one for a missing round would
silently misrepresent absence-of-data as neutral-opinion, which is
exactly the kind of silent incorrect result section 27 asks us to avoid.

## 4. Opinion change (section 8)

`src/opinion_change/change_calculator.py` computes:
```
change = stance(round B) - stance(round A)
```
between an agent's own **consecutive available** data points — not
strictly `round N` vs `round N-1` by number. If an agent is missing a
round (e.g. has rounds 1 and 3 but not 2), the resulting
`OpinionChangePoint` explicitly records `from_round=1, to_round=3`, so
the gap is visible rather than silently interpolated or skipped without
a trace. This satisfies the acceptance criterion that "the trajectory of
each agent [is] inspectable."

## 5. Data validation (section 27)

Two severities, both in `discussion_loader.py`:

- **Fatal** (`DiscussionValidationError`, load aborts entirely): file
  missing, invalid JSON, or a genuinely empty discussion (no
  participants and no opinion history at all — nothing to analyze).
- **Warning** (collected in `ValidationReport`, load still succeeds):
  a participant with no opinion data, opinion data for an
  unlisted agent, a snapshot missing its round number, a snapshot with
  missing/malformed stance, a duplicate snapshot for the same
  `(agent, round)` (first occurrence kept — documented choice, since
  Week 3 appends chronologically and a later duplicate more likely
  indicates a bug than a correction), and an out-of-range stance value
  (clamped to `[-1, 1]`).

This is intentionally not "an enormous validation framework" (per the
README's own guidance) — it validates exactly what Opinion Change needs
(`participants` + `opinion_history`), not message/graph structure needed
by the other three analytics categories that are out of scope here.

## 6. Handling missing data (section 28)

`compute_opinion_change()` explicitly enforces the section 28
requirement — "Opinion change requires multiple stance snapshots" — as
checked, not assumed:

| Situation | Result |
|---|---|
| 0 stance points for an agent | `AgentChangeResult(changes=[], reason="No stance snapshots available...")` |
| 1 stance point for an agent | `AgentChangeResult(changes=[], reason="Only one stance snapshot available...")` |
| 2+ stance points | `changes` populated, one entry per consecutive pair |

`AgentChangeResult.is_computable` lets a caller check this without
string-matching the reason. No metric is ever silently reported as
`0.0` change when it was actually *not computable*.

## 7. What is explicitly NOT implemented

- Agreement/Disagreement scoring (section 9-11).
- Influence metrics (section 12-16).
- The unified Analytics Engine interface across all four categories
  (section 17-19).
- Report generation and visualizations (section 20-26).
- Reproducibility tooling / CLI beyond the `main.py` demo (section 29).

These map directly onto later README sections and are natural next
steps on top of this data layer.
