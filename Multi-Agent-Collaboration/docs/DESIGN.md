# Design Decisions — Sections 6, 7, 8, 9, 10, 21

This document covers only the scope tackled in this pass: the agent
graph and the round-based discussion orchestrator. Retrieval-during-
discussion, persistence, and opinion tracking (sections 11-20, 22-23)
are deliberately out of scope here and are a follow-up.

## 1. How the graph is created (section 8.1)

`AgentGraph.ring(agent_ids)` builds a directed cycle over the given
agent ids: `agent[0] -> agent[1] -> ... -> agent[-1] -> agent[0]`.

`AgentGraph.from_edges(agent_ids, extra_edges)` builds that same ring,
then adds any additional directed edges supplied by the caller (e.g.
persona-based relationships decided at discussion-setup time).

## 2. Why this approach (section 8.2)

- A directed cycle is the *minimal* structure that is guaranteed
  strongly connected for any N >= 2 agents (N edges, one path all the
  way around).
- It is fully determined by the agent id ordering, so it is trivially
  reproducible and inspectable (`graph.as_dict()`).
- It supports a natural round-robin turn order for the orchestrator: in
  the base ring, each agent has exactly one designated downstream
  listener, which maps directly onto "who reacts to whom" in a
  discussion.
- Extra edges *can* be layered on top of the base ring (via `AgentGraph.
  from_edges`) to let two non-adjacent agents communicate directly,
  without ever weakening connectivity. The current demo (`main.py`)
  deliberately keeps to the plain ring with no extra edges, since a
  simple "everyone reacts to the one before them" chain was judged
  clearer to reason about for four agents than adding a cross-graph
  shortcut with no strong justification for that specific pair. The
  `from_edges` capability remains available for a future persona-based
  relationship that actually motivates a shortcut.

Rejected alternatives: a fully connected (complete) graph was
considered simplest but was rejected because the spec explicitly
discourages plain broadcast-to-everyone unless justified (section 11);
a randomly generated graph was rejected for this pass because it
sacrifices reproducibility for no clear benefit at this small agent
count.

## 3. How strong connectivity is guaranteed (section 8.3)

Constructively: the base ring already satisfies the strongly-connected
definition (every node reachable from every other node), and adding
edges can only add reachability, never remove it.

Additionally verified, not just assumed: `AgentGraph.is_strongly
_connected()` runs two BFS passes from an arbitrary start node — one
over the graph as given, one over the reversed graph — and confirms
both reach every node. Every constructor (`ring`, `from_edges`) calls
this check internally and raises `ValueError` if it ever fails, making
connectivity a checked invariant rather than a hopeful assumption.
This is exercised directly in `tests/test_graph.py`.

## 4. How the graph affects discussion behavior (section 8.4)

`DiscussionOrchestrator.run()` uses `graph.nodes` order to decide which
agent speaks next within a round, and `graph.neighbors(agent_id)` to
decide who receives that agent's message (see `src/orchestration/
orchestrator.py`). An agent's incoming context for its next turn is
exactly the set of messages ever routed to it by the graph — so an
agent with more incoming edges accumulates more to react to, and an
agent with more outgoing edges shapes more of the discussion per round.
This is what makes the graph a real routing mechanism (section 11)
rather than cosmetic structure.

## 5. Orchestration model (sections 9-10)

One round = every agent in `graph.nodes` speaks exactly once, in graph
node order. Before speaking, an agent receives every message routed to
it so far (accumulated across all previous rounds, not just the
current one) via `trace.messages_for(agent_id)`. After speaking, the
message is appended to the shared `DiscussionTrace` and routed to
`graph.neighbors(agent_id)`. This repeats for `num_rounds` (minimum 3,
enforced by `DiscussionOrchestrator.__init__`).

## 6. Termination (section 21)

Only the spec's minimum-viable rule is implemented: the discussion ends
once `num_rounds` rounds have completed. This is intentional for this
pass — more sophisticated termination (convergence, no meaningful
opinion change, moderator decision) requires opinion tracking
(sections 18-19), which is out of scope here. `DiscussionTrace.
termination_reason` records why the run ended, so a future
convergence-based rule can slot in without changing the trace's shape.

## 7. Real Week 2 agents

- `src/adapters/week2_agent_adapter.py` wraps a real Week 2 `BaseAgent`
  (persona + LLM + tools + memory) behind the `DiscussionAgent`
  protocol, using the same sibling-repo direct-import pattern (and the
  same `src`-package-name-collision fix) as Week 2's own
  `knowledge_retrieval_tool.py`. `main.py` is the single entry
  point: it runs a real 3-round discussion with all four Week 2
  personas, calling the actual OpenRouter LLM and actual tools
  (`get_match_summary`, `get_match_opinions`, `web_search`,
  `get_knowledge`) each turn.

(An earlier dependency-free demo using stand-in `EchoAgent` objects
existed during initial development to validate the graph/orchestration
mechanics in isolation from any LLM. It has since been removed in
favor of testing that mechanics directly via `tests/test_orchestrator.py`,
which uses an equivalent lightweight `StubAgent` — so the same
no-API-key test coverage still exists, just inside the test suite
rather than as a separate runnable script.)

## 8. What is still NOT implemented

- Mid-discussion retrieval as an *explicit, on-demand* action (currently
  `knowledge_base_analyst` always retrieves once per turn via its
  existing tool wiring, rather than deciding *when* retrieval is useful
  mid-discussion — section 14/15's "agent decides when to retrieve").
- Persisting `DiscussionTrace` to disk (section 16/17).
- Opinion snapshots / opinion evolution tracking (section 18/19).
- Discussion run identity (unique run ids) for reproducibility (section 17).

These map directly onto README sections 14-20 and 22-23 and are the
natural next steps on top of this foundation.
