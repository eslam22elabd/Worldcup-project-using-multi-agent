# Design Decisions — Sections 9-16 (Agreement & Influence)

This document extends `DESIGN.md` (which covers sections 4, 6, 7, 8, 27, 28
for Opinion Change) with the Agreement and Influence metrics.

---

## 1. Agreement / Disagreement (sections 9-11)

### Metric Documentation (section 36 template)

```
Metric:       Agreement Score
Purpose:      Measure how aligned or divided the group is during each round.
Input:        Per-agent stance values for a given round (from stance_series).
Formula:      Agreement(r) = 1.0 - avg_pairwise_diff / 2.0
Output:       One float per round, or None if not computable.
Range:        [0.0, 1.0]
Interpretation:
    1.0    = perfect consensus (all stances identical)
    0.0    = maximum polarization (agents at -1.0 and +1.0)
    > 0.75 = high agreement
    < 0.50 = strong divergence
Limitations:
    - Treats all agents equally (no weighting by confidence or activity).
    - Sensitive to the number of agents: a single outlier has less
      effect in a large group than in a small one.
    - Based on lexical-heuristic polarity from Week 3, not semantic
      similarity of the opinions themselves.
```

### Formula details

For each round `r` with `N >= 2` agents that have valid stance data:

1. Collect stances: `S = {s_1, s_2, ..., s_N}`, each in `[-1.0, 1.0]`.
2. Compute all pairwise absolute differences:
   `d(i, j) = |s_i - s_j|`  for all `i < j`.
   There are `P = N*(N-1)/2` such pairs.
3. Average: `d_avg = sum(d(i,j)) / P`.
4. Normalize by the maximum possible difference (2.0):
   `d_norm = d_avg / 2.0`, which lies in `[0.0, 1.0]`.
5. Agreement: `Agreement(r) = 1.0 - d_norm`.

### Edge cases (section 28)

| Situation | Result |
|-----------|--------|
| 0 agents with stance data in a round | `score=None`, `reason="Agreement requires at least 2 agents..."` |
| 1 agent with stance data in a round | `score=None`, same reason |
| 2+ agents | Score computed normally |

---

## 2. Influence (sections 12-16)

### Metric Documentation (section 36 template)

```
Metric:       Influence Score (DeGroot-inspired directional alignment)
Purpose:      Estimate how much each agent's arguments are associated
              with opinion changes in the agents they communicate with.
Input:        Per-agent stance series, directed interaction graph
              (sender/recipient per round from Week 3 export).
Formula:      influence(i) = dot(X, Y) / (||X|| * ||Y||)
              where X = stance pulls, Y = recipient changes.
Output:       One float per agent, or None if not computable.
Range:        [-1.0, 1.0]
Interpretation:
    +1.0   = perfect positive association: peers always move toward
             this agent's position after hearing from them.
     0.0   = no association between this agent's stance pull and
             subsequent peer opinion changes.
    -1.0   = perfect contrarian effect: peers always move AWAY from
             this agent's position.
Limitations:
    - This is an ASSOCIATION metric, not causal proof (section 37).
      A high score means peer changes are correlated with the agent's
      stance direction, not that the agent CAUSED those changes.
    - Limited by sample size: with a ring topology and 3 rounds,
      each agent only gets ~2 observation pairs.
    - Based on lexical-heuristic polarity, not semantic content.
    - Does not account for confounding factors (e.g., a third agent
      influencing both the sender and recipient simultaneously).
```

### DeGroot-inspired formulation

The DeGroot opinion dynamics model says agents update their opinions as
weighted averages of their neighbors' opinions.  We test whether this
pattern holds in the actual discussion data.

For each agent `i` that sends messages to peers, we collect observation
pairs `(X, Y)` across all rounds `r` where both endpoints have data:

- `X = s_i(r) - s_j(r)` — the **stance pull**: how far sender `i` is
  from recipient `j` in round `r`.  Positive means `i` is above `j`;
  negative means `i` is below `j`.
- `Y = s_j(r+1) - s_j(r)` — the **recipient's subsequent change**: how
  much `j` moved from round `r` to round `r+1`.

If agent `i` is influential in a DeGroot sense, peers tend to move
toward `i`'s position:
- When `X > 0` (i above j), `Y > 0` (j moves up).
- When `X < 0` (i below j), `Y < 0` (j moves down).

This gives a positive dot product between X and Y vectors.

The score is the **cosine similarity** of the X and Y vectors:

```
influence(i) = dot(X, Y) / (||X|| * ||Y||)
```

We intentionally do NOT center X and Y (which would give Pearson
correlation) because the natural zero points — `X=0` means "same
stance" and `Y=0` means "no change" — are already meaningful anchors.

### Interaction extraction

The influence calculation uses directed communication edges from the
Week 3 export.  The export contains:

1. **`rounds`**: `round_1`, `round_2`, etc., each with messages that
   have `sender`, `recipients`, and `content` fields.
2. **`graph`**: static topology with `nodes` and `edges`.

We primarily use the per-round messages (more accurate, since they
show who actually communicated in each round).  If message data is
unavailable, we fall back to the static graph edges replicated across
all rounds.

### Edge cases (section 16)

| Situation | Result |
|-----------|--------|
| < 2 rounds total | `score=None`, all agents: "at least 2 rounds required" |
| Agent has no outgoing interactions | `score=None`: "no outgoing communication interactions" |
| All X values ≈ 0 (sender = recipients) | `score=None`: "zero stance pull" |
| All Y values ≈ 0 (no peer changes) | `score=None`: "no opinion changes observed in recipients" |
| Only 1 observation pair | `score=None`: "need at least 2 for meaningful correlation" |

### Interpretation vs Measurement (section 37)

```
"web_search_analyst has an influence score of -1.0"
```

is a **measurement** (correlation-based association).

```
"web_search_analyst caused tactical_analyst to change opinion"
```

is a much stronger **causal claim** that this metric does NOT support.

The correct interpretation is:

```
"Changes in tactical_analyst's stance were negatively associated
 with web_search_analyst's relative stance direction."
```

---

## 3. What is explicitly NOT implemented (left to teammates)

- Sentiment analysis (Part 3 — Teammate 3).
- Unified Analytics Engine combining all four categories (Part 3).
- Report generation (Part 4 — Teammate 4).
- Visualizations: opinion trajectory chart, interaction graph (Part 4).
