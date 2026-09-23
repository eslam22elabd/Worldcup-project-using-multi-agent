# Routing & Discussion State Architecture (Task 2)

This document details the design and implementation of **Message Routing** (`src/routing/`) and **Discussion State** (`src/state/`), fulfilling Week 3 Spec requirements:
- **Sections 4.3, 11, 12, 13**: Graph-Based Message Routing & Context
- **Sections 16, 17, 20, 30**: Discussion State, Run Identity, and Checkpointing

---

## 1. Architectural Separation

Following Spec Section 34 (*Engineering Considerations*), the discussion engine enforces strict decoupling:

```text
┌─────────────────────────────────────────────────────────────┐
│                      BaseAgent (Week 2)                     │
└──────────────────────────────┬──────────────────────────────┘
                               │ speak()
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    DiscussionOrchestrator                   │
│  - Coordinates rounds (1..N)                                │
│  - Retrieves incoming context from MessageRouter            │
│  - Dispatches messages to MessageRouter                     │
│  - Advances DiscussionState lifecycle                       │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               │ routes messages              │ updates state,
               ▼                              │ captures checkpoints
┌─────────────────────────────┐  ┌────────────▼───────────────┐
│        MessageRouter        │  │       DiscussionState       │
│                             │  │                             │
│  - Resolves recipients via  │  │  - Unique discussion_id    │
│    graph outgoing edges     │  │  - Active round & status   │
│  - Ring & multi-neighbor    │  │  - Ordered message log     │
│    routing                  │  │  - Checkpoints per round   │
│  - Manages agent inboxes    │  │  - to_dict() / from_dict() │
│  - Assembles prompt context │  │  - Opinion tracking hooks  │
│  - Extensible filter hooks  │  │    (for Teammate 3)        │
│    (for Teammate 4)         │  │  - Retrieval event hooks   │
└─────────────────────────────┘  │    (for Teammate 4)        │
                                 └────────────────────────────┘
```

---

## 2. Message Routing (`src/routing/router.py`)

### 2.1 How Recipients Are Resolved
- An agent's outgoing edges (`graph.neighbors(sender_id)`) determine message recipients.
- **No Broadcast**: Messages are delivered only to designated neighbors. In a ring $A \to B \to C \to A$, a message from $A$ is routed only to $B$. In a graph with extra shortcut edges ($A \to B$ and $A \to C$), $A$ routes to both $B$ and $C$.
- Raises `ValueError` if an unregistered sender attempts to transmit.

### 2.2 Agent Inbox Management
`router.get_agent_inbox(agent_id, state, current_round_only=False)`:
- Extracts messages where `agent_id in message.recipient_ids`.
- Preserves chronological arrival sequence and round numbers.
- Supports querying cumulative context across all previous rounds or restricting to the current active round.

### 2.3 Context Prompt Assembly
`router.format_agent_context(agent_id, incoming_messages)`:
- Formats incoming messages with clear attribution:
  ```text
  --- [Round 1] Analyst 'match_summary_analyst' ---
  "Mexico's high-pressing yielded 0.82 VAEP in the first half..."
  ```
- Ensures agents react to specific neighbor arguments rather than speaking in isolation.

### 2.4 Extensible Filter Hooks
Teammates can register custom routing filters:
```python
def topic_filter(sender_id: str, recipients: list[str], metadata: dict) -> list[str]:
    # Custom condition: e.g., only route if relevance threshold met
    return recipients

router.register_filter(topic_filter)
```

---

## 3. Discussion State (`src/state/discussion_state.py`)

### 3.1 State Schema
A single `DiscussionState` instance contains:
- `discussion_id`: Unique identifier (e.g. `disc_a1b2c3d4e5f6`).
- `topic`: The match or discussion subject.
- `participants`: List of active agent IDs.
- `graph_config`: Graph nodes and adjacency map.
- `current_round`: 1-indexed active round (0 before start).
- `num_rounds`: Target rounds (enforced $\ge 3$).
- `status`: Lifecycle enum (`INITIALIZING` $\to$ `IN_PROGRESS` $\to$ `ROUND_COMPLETE` $\to$ `COMPLETED`).
- `messages`: Chronological list of typed `Message` instances.
- `opinions`: Dictionary mapping `agent_id -> list[opinion_record]`.
- `retrieval_events`: List of recorded mid-discussion retrieval events.
- `checkpoints`: Round boundary snapshots.
- `started_at` / `completed_at`: UTC ISO-8601 timestamps.
- `termination_reason`: Explanation of run termination.

### 3.2 State Serialization
- `state.to_dict()`: Full JSON-serializable dictionary conforming to Spec Section 30.
- `DiscussionState.from_dict(data)`: Lossless reconstruction of the typed state.

---

## 4. Teammate Handoff & Integration Guide

### 4.1 Guide for Teammate 3 (Persistence & Opinion Tracking)

#### Saving to Disk / Database (Persistence)
`DiscussionState` is fully serializable. To persist a completed discussion:
```python
import json
from src.state.discussion_state import DiscussionState

# Save state to JSON file
state_dict = state.to_dict()
with open(f"data/{state.discussion_id}.json", "w") as f:
    json.dump(state_dict, f, indent=2)

# Load state back from JSON
with open(f"data/{state.discussion_id}.json", "r") as f:
    loaded_state = DiscussionState.from_dict(json.load(f))
```

#### Tracking Opinion Evolution
Use `state.record_opinion(...)` to capture agent opinions per round:
```python
state.record_opinion(
    agent_id="match_summary_analyst",
    round_number=1,
    opinion="Mexico dominated possession and created superior xT chances.",
    stance={"polarity": 0.75, "consensus_agreement": True}, # Optional structured stance
    metadata={"model": "gpt-4o", "confidence": 0.9}
)

# Query opinions for an agent:
history = state.opinions["match_summary_analyst"]
for record in history:
    print(record["round"], record["opinion"], record["stance"])
```

---

### 4.2 Guide for Teammate 4 (Mid-Discussion Retrieval & Demo)

#### Logging Retrieval Events
When an agent invokes a tool to retrieve evidence mid-discussion:
```python
state.record_retrieval(
    agent_id="knowledge_base_analyst",
    round_number=2,
    query="World Cup 2010 Mexico vs South Africa tactical lineups",
    evidence=["Tshabalala scored opening goal; Marquez equalized in 79th min."],
    tool_name="get_knowledge",
    metadata={"k": 3, "score": 0.88}
)

# Inspect all retrieval events in the run:
for event in state.retrieval_events:
    print(f"[{event['agent_id']} in Round {event['round']}] {event['query']}")
```

#### Running the Demo & Inspecting Routing
In `main.py`:
```python
orchestrator = DiscussionOrchestrator(graph=graph, agents=agents, num_rounds=3)
state = orchestrator.run(topic=TOPIC)

# Access routed messages:
for msg in state.messages:
    print(f"[Round {msg.round_number}] {msg.sender_id} -> {msg.recipient_ids}")

# Verify discussion checkpoints:
for chk in state.checkpoints:
    print(f"Checkpoint: {chk['label']} at round {chk['current_round']}")
```

---

## 5. Verification & Test Coverage

The test suite validates routing and state mechanics independently of external LLMs or databases:

```powershell
python -m pytest tests/ -v
```

- **`tests/test_graph.py`**: Strong connectivity invariants.
- **`tests/test_orchestrator.py`**: Multi-round execution ($\ge 3$ rounds) and backward compatibility with `DiscussionTrace`.
- **`tests/test_routing.py`**: Topological recipient resolution, ring routing, multi-recipient shortcut routing, non-leakage, and context formatting.
- **`tests/test_state.py`**: State lifecycle transitions, message log, opinion & retrieval hooks, and lossless serialization roundtrip.
