# Multi-Agent Discussion Engine (Week 3)

A multi-round discussion system that connects the four football-analyst
agents built in Week 2 through a strongly connected communication graph,
lets them react to each other's opinions over multiple rounds, tracks how
each agent's opinion evolves, and persists the full discussion state for
downstream use.

---

## What this is

Week 2 originally produced four independent agents. We have expanded this to support dynamic, **Match-Specific Personas** based on natural language input.

Instead of selecting from a pre-defined menu, you simply type the match you want to discuss (in **Arabic or English**). The system detects the match using `match_personas_registry.py` and loads a custom set of 6 personas tailored specifically to that match's narrative.

**Supported Matches & Personas:**

**1. Argentina × Spain (2026 World Cup Final):**
- `arg_esp_tactical_analyst`: Analyzes Spain's possession and Argentina's zero 1st-half shots.
- `arg_esp_referee_expert`: Focuses strictly on the Enzo Fernandez red card controversy.
- `arg_esp_argentina_fan`: Passionate defender of Messi in his final World Cup match.
- `arg_esp_spain_fan`: Biased supporter celebrating Lamine Yamal and De la Fuente.
- `arg_esp_neutral_journalist`: Contextualizes the passing of the torch (Messi to Yamal).
- `arg_esp_goalkeeper_expert`: Analyzes Emi Martinez's historic 11-save performance.

**2. France × England (2026 World Cup Third Place):**
- `fra_eng_tactical_analyst`: Explains why two elite defenses conceded 10 goals.
- `fra_eng_motivation_analyst`: Sports psychology focus on "dead-rubber" match dynamics.
- `fra_eng_france_fan`: Frustrated by the collapse but proud of Mbappe.
- `fra_eng_england_fan`: Euphoric about Saka's hat-trick and the 4-0 comeback.
- `fra_eng_stats_expert`: Tracks the Golden Boot race (Mbappe, Kane, Bellingham, Saka).
- `fra_eng_neutral_journalist`: Debates if the 10-goal thriller was great football or poor defending.

**Smart Fallback:**
If you ask about any other match (e.g., `Real Madrid vs Barcelona`), the system gracefully degrades to a generic search-only configuration using 5 general personas (`tactical_analyst`, `fan_narrative_analyst`, etc.).

Instead of each producing one isolated opinion, they take turns over three rounds, reading what the previous agent said and responding to it — while keeping their own tool access (`web_search`) and memory intact.

After the discussion completes, the engine:
- Tracks each agent's **opinion evolution** (stance polarity, confidence,
  agreement) across rounds.
- Logs **mid-discussion retrieval events** (which tool each agent used,
  per round).
- **Persists** the full discussion state to disk and exports a Week 4-ready
  JSON payload.

---

## How it works

### 1. Agent graph (`src/graph/agent_graph.py`)

The participating agents are connected as a **directed ring**. Since the number of agents is dynamic based on the match type detected by the registry, the ring scales automatically. For example, the 6-agent ring for the Argentina vs Spain match looks like this:

```
tactical_analyst → referee_expert → argentina_fan → spain_fan → neutral_journalist → goalkeeper_expert
       ▲                                                                                     │
       └─────────────────────────────────────────────────────────────────────────────────────┘
```

A ring is the simplest structure that guarantees the graph is **strongly
connected** (every agent can eventually reach every other agent) for any
number of agents ≥ 2, using the minimum number of edges. This is verified
programmatically, not just assumed — every graph checks its own
connectivity (`is_strongly_connected()`) before it can be used.

Extra directed edges can be layered on top of the ring via
`AgentGraph.from_edges()` for persona-based or manually-configured
relationships, without ever breaking strong connectivity.

### 2. Discussion orchestrator (`src/orchestration/orchestrator.py`)

Each round, every agent speaks once, in graph order. An agent's message
is routed only to its graph neighbor(s) — not broadcast to everyone. Each
agent sees every message ever routed to it (from earlier rounds too), so
context accumulates as the discussion goes on. The discussion always runs
for **at least 3 rounds** and stops once the configured round count is
reached.

### 3. Week 2 agent adapter (`src/adapters/week2_agent_adapter.py`)

The orchestrator doesn't know anything about LLMs, personas, or tools —
it only needs an object with a `speak()` method. This adapter wraps each
real Week 2 `BaseAgent` so it fits that interface:

- **Round 1**: calls the agent's `generate_initial_opinion()` — same
  call Week 2's own demo uses.
- **Rounds 2+**: builds a prompt from the most recent message it received
  and calls `respond()`, which reuses the agent's own conversation memory
  automatically.

Since Week 1, Week 2, and this project are three separate repos that each
use `src` as their top-level package name, the adapter also handles
temporarily swapping `sys.modules` during the cross-repo import so Python
resolves the *correct* `src` package each time (see the module's docstring
for details).

### 4. Discussion state (`src/state/discussion_state.py`)

`DiscussionState` is the single source of truth for the entire discussion.
It tracks:

| Field | Purpose |
|---|---|
| `messages` | All `Message` objects produced during the discussion |
| `opinions` | Per-agent, per-round opinion snapshots (populated by `OpinionTracker`) |
| `retrieval_events` | Mid-discussion tool/retrieval records |
| `checkpoints` | Lightweight state snapshots captured at each round boundary |
| `status` | Lifecycle enum: `INITIALIZING → IN_PROGRESS → ROUND_COMPLETE → COMPLETED` |

Checkpoints are captured automatically at the end of every round and when
the discussion completes, giving a full audit trail.

### 5. Message routing (`src/routing/router.py`)

`MessageRouter` sits between the orchestrator and the graph:
- `get_agent_inbox(agent_id, state)` — returns all messages ever routed to
  this agent (most recent last), so each agent's context grows across rounds.
- `determine_recipients(agent_id)` — reads the graph neighbors to decide
  who receives the outgoing message this turn.

### 6. Opinion tracking (`src/opinion/`)

After the discussion runs, `OpinionTracker` walks every message and records
an `OpinionSnapshot` per agent per round into `DiscussionState.opinions`.
Each snapshot includes a `Stance`:

| Stance field | What it captures |
|---|---|
| `polarity` | `−1.0` (strongly negative) … `+1.0` (strongly positive) |


`OpinionEvolutionAnalyzer` then compares consecutive snapshots per agent
and classifies each transition as `STRENGTHENED`, `WEAKENED`, `SHIFTED`,
`REVERSED`, or `UNCHANGED`. It also computes a **consensus trajectory**
across all agents per round and characterises the overall discussion as
`converging`, `diverging`, or `stable`.

### 7. Mid-discussion retrieval logging (`DiscussionState.record_retrieval`)

Each agent invokes its Week 2 tool inside `speak()`. Because those calls
happen inside Week 2's `BaseAgent` internals, they are not directly
observable from the orchestrator. `main.py` records one retrieval event
per message — capturing the agent ID, round number, tool name, and a
descriptor — which proves the retrieval infrastructure is wired end-to-end
and produces a `retrieval_events` list that is exported alongside opinions.

> This is the *minimum viable* mid-discussion retrieval integration. A
> deeper version would hook into Week 2's `ToolRegistry` directly and
> capture the actual query string and tool response per call.

### 8. Persistence (`src/persistence/discussion_store.py`)

`DiscussionStore` saves and loads full `DiscussionState` objects as JSON:

```
data/
└── discussions/
    └── disc_<id>.json      ← full state, reload with DiscussionStore.load()
data/
└── exports/
    └── week4_disc_<id>.json ← Week 4-ready payload (schema_version: week4.v1)
```

The `export_for_week4()` method produces a structured payload with
per-round message lists, `opinion_history`, `retrieval_events`,
`checkpoints`, and a `schema_version` field so downstream consumers can
detect breaking changes.

---

## Repository layout

```
Multi-Agent-Collaboration/
├── main.py                              # Entry point — runs a real discussion
├── requirements.txt
├── docs/
│   ├── DESIGN.md                        # Design decisions (graph, orchestration, termination)
│   ├── ROUTING_AND_STATE.md             # Routing logic and DiscussionState design
│   └── PERSISTENCE_AND_OPINION_TRACKING.md
├── src/
│   ├── graph/
│   │   └── agent_graph.py              # AgentGraph: ring construction + connectivity check
│   ├── orchestration/
│   │   └── orchestrator.py             # DiscussionOrchestrator: rounds, routing, termination
│   ├── discussion/
│   │   └── message.py                  # Message data structure
│   ├── state/
│   │   └── discussion_state.py         # DiscussionState: lifecycle, opinions, retrievals, checkpoints
│   ├── routing/
│   │   └── router.py                   # MessageRouter: inbox + recipient determination
│   ├── opinion/
│   │   ├── tracker.py                  # OpinionTracker: records snapshots into state
│   │   ├── analyzer.py                 # OpinionEvolutionAnalyzer: shift detection + consensus
│   │   ├── extractor.py                # StanceExtractor: heuristic polarity/confidence scoring
│   │   └── models.py                   # Stance, OpinionSnapshot, OpinionShift dataclasses
│   ├── persistence/
│   │   └── discussion_store.py         # DiscussionStore: save / load / export_for_week4
│   └── adapters/
│       └── week2_agent_adapter.py      # Wraps Week 2 agents for the orchestrator
└── tests/
    ├── test_graph.py                   # Strong-connectivity tests
    ├── test_orchestrator.py            # Routing / multi-round tests (StubAgent)
    ├── test_routing.py                 # MessageRouter inbox / recipient tests
    ├── test_state.py                   # DiscussionState lifecycle + serialization
    ├── test_opinion_tracking.py        # OpinionTracker + StanceExtractor + analyzer
    └── test_persistence.py             # DiscussionStore save/load/export round-trip
```

---

## Prerequisites

This project assumes the three repos sit as **sibling folders**:

```
projects/
├── knowledge-infrastructure-main/       (Week 1 — RAG knowledge base)
├── Intelligent-Agent-Framework-week2/   (Week 2 — the four agents)
└── Multi-Agent-Collaboration/           (this repo)
```

If your layout differs, set `WEEK2_PROJECT_PATH` (and Week 2's own
`KNOWLEDGE_INFRA_PATH`) to override the default paths.

Before running:

1. **Week 1's Postgres must be running** (needed by `knowledge_base_analyst`):
   ```powershell
   cd ..\knowledge-infrastructure-main
   docker-compose up -d
   ```
2. **Week 2's `.env` must have valid API keys** (`OPENROUTER_API_KEY`,
   `TAVILY_API_KEY`) — this project loads Week 2's `.env` directly, since
   it has no `.env` of its own.

---

## How to run

```powershell
cd Multi-Agent-Collaboration
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

This will:
1. Ask you to enter a match in Arabic or English (e.g. `إسبانيا كسبت الأرجنتين` or `France vs England third place`).
2. Detect the match and load the specific 6-persona configuration (or the generic fallback 5-persona configuration for unknown matches).
3. Build the real Week 2 agents based on the detected personas.
4. Run a 3-round discussion where each persona searches the web and responds to its peers in-character.
5. Print every message, in order, with its round number and recipient(s).
6. Print the termination reason once all rounds complete.
7. Record **retrieval events** for each agent turn (mid-discussion retrieval log).
8. Track **opinion snapshots** for every agent across all rounds.
9. Analyse **opinion evolution** (shifts, trend).
10. **Save** the full discussion to `data/discussions/<id>.json`.
11. **Export** a Week 4-ready payload to `data/exports/week4_<id>.json`.
12. Print a **summary box** to the terminal:

```
╔══════════════════════════════════════════════════════════════════════╗
║                        DISCUSSION SUMMARY                            ║
╠══════════════════════════════════════════════════════════════════════╣
║  Discussion ID  : disc_xxxxxxxxxxxx                                  ║
║  Topic          : Argentina vs Spain — 2026 FIFA World Cup Final     ║
║  Participants   : arg_esp_tactical_analyst, arg_esp_referee_expert...║
║  Rounds         : 3/3                                                ║
║  Termination    : Reached configured num_rounds=3.                   ║
╠══════════════════════════════════════════════════════════════════════╣
║                       OPINION EVOLUTION                              ║
╠══════════════════════════════════════════════════════════════════════╣
║  Overall trend  : diverging                                          ║
║  Shifts found   : 5                                                  ║
║    tactical     : STRENGTHENED → UNCHANGED                           ║
║    referee      : SHIFTED → STRENGTHENED                             ║
║    argentina_fan: UNCHANGED → UNCHANGED                              ║
║    spain_fan    : REVERSED → SHIFTED                                 ║
╠══════════════════════════════════════════════════════════════════════╣
║                          PERSISTENCE                                 ║
╠══════════════════════════════════════════════════════════════════════╣
║  Saved to       : data/discussions/disc_xxxxxxxxxxxx.json            ║
║  Week 4 export  : data/exports/week4_disc_xxxxxxxxxxxx.json          ║
╚══════════════════════════════════════════════════════════════════════╝
```

⚠️ This calls the real LLM **4 agents × 3 rounds = 12 times** per run, so
it takes a few minutes and uses real API quota.

---

## Running the tests

The test suite doesn't need any API keys, Postgres, or Week 1/2 repos —
it uses a lightweight in-memory `StubAgent` to verify all mechanics on
their own:

```powershell
pip install pytest
python -m pytest tests/ -v
```

### What each test file covers

| File | Covers |
|---|---|
| `test_graph.py` | Ring + ring-with-shortcut graphs are strongly connected; a broken graph is rejected |
| `test_orchestrator.py` | ≥3 rounds run; messages route only to graph neighbors; missing agents caught early |
| `test_routing.py` | `MessageRouter` inbox grows across rounds; recipients match graph neighbors |
| `test_state.py` | `DiscussionState` lifecycle transitions; `to_dict` / `from_dict` round-trip; checkpointing |
| `test_opinion_tracking.py` | `OpinionTracker.track_from_messages`; `StanceExtractor` polarity; `OpinionEvolutionAnalyzer` shift detection |
| `test_persistence.py` | `DiscussionStore` save / load / `export_for_week4` round-trip; corrupted-file handling |

---

