# Task 3: Persistence and Opinion Tracking

This document explains the implementation of **Discussion Persistence** (`src/persistence/`) and **Opinion Tracking** (`src/opinion/`) for Week 3.

---

## 1. Overview

Task 3 takes the messages produced during a multi-agent discussion and does two main things:
1. **Opinion Tracking**: captures each agent's opinion across rounds (Initial, Round 1, Round 2, Round 3), extracts their stance (polarity and confidence), and checks whether their opinion changed, how it changed, and when.
2. **Persistence**: saves the complete discussion to disk as structured JSON so it can be reloaded later or exported directly for Week 4 analytics.

---

## 2. Persistence (`src/persistence/discussion_store.py`)

### How it works
- Discussions are stored as JSON files under `data/discussions/{discussion_id}.json`.
- `DiscussionStore.save(state)` takes a `DiscussionState` object and writes it to disk. To prevent corrupting files if a run crashes midway, it writes to a temporary `.tmp` file first and then renames it.
- `DiscussionStore.load(discussion_id)` reads the JSON file and reconstructs the full `DiscussionState` using `DiscussionState.from_dict()`.
- `DiscussionStore.list_discussions()` lists all saved runs in the folder with summary info (topic, rounds, message count, timestamps).
- `DiscussionStore.export_for_week4(state)` formats the discussion into the schema required by Week 4 analytics (organizing messages by round, attaching retrieval events, and grouping each agent's opinion history).

---

## 3. Opinion Tracking (`src/opinion/`)

### Opinion Representation (`models.py`)
Each opinion snapshot contains:
- `agent_id`: which agent spoke.
- `round_number`: 0 for the pre-discussion initial opinion, and 1, 2, 3... for post-round opinions.
- `opinion_text`: the text of the agent's response.
- `stance`: a structured `Stance` object with:
  - `polarity` (float from -1.0 to +1.0): -1.0 means strongly negative or critical, +1.0 means strongly positive or confident, and 0.0 is neutral/balanced.
  - `confidence` (float from 0.0 to 1.0): certainty of the claim.
  - `key_arguments`: list of key sentences supporting the stance.
  - `agreement_score` (float from 0.0 to 1.0): how much the agent agreed with the previous message it received.

### Stance Extractor (`extractor.py`)
A lightweight rule-based extractor that checks for positive, negative, and confidence keywords to estimate polarity and confidence offline without needing API calls or external models during tests.

### Tracking Across Rounds (`tracker.py`)
`OpinionTracker` records opinions into `DiscussionState`:
- `record_initial_opinion(state, agent_id, opinion)`: records Round 0.
- `record_round_opinion(state, agent_id, round_number, opinion)`: records Round 1, 2, 3...
- `track_from_messages(state)`: convenience function that reads all messages in `state.messages` and automatically records opinion snapshots for each agent per round.

### Opinion Evolution & Change Detection (`analyzer.py`)
`OpinionEvolutionAnalyzer` compares an agent's opinion from one round to the next:
- `delta_polarity = new_polarity - old_polarity`
- `delta_confidence = new_confidence - old_confidence`

It classifies changes using the categories from the spec:
- **strengthened**: position became more extreme in the same direction, or confidence increased.
- **weakened**: position moved closer to neutral, or confidence dropped.
- **shifted**: position moved noticeably toward another view.
- **reversed**: polarity flipped from positive to negative or vice versa.
- **unchanged**: changes were within a small threshold (0.10).

It also calculates **group consensus** per round by measuring the spread (standard deviation) of polarities across all agents. If the spread decreases over rounds, the agents are moving toward consensus; if it increases, they are polarizing.

---

## 4. Handoff for Teammate 4 (Retrieval + Demo)

In `main.py`, you can run the discussion, track opinions, analyze shifts, and save the result in just a few lines:

```python
from src.orchestration.orchestrator import DiscussionOrchestrator
from src.opinion import OpinionTracker, OpinionEvolutionAnalyzer
from src.persistence import DiscussionStore

# 1. Run the discussion
orchestrator = DiscussionOrchestrator(graph=graph, agents=agents, num_rounds=3)
state = orchestrator.run(topic=TOPIC)

# 2. Track opinions from the messages
tracker = OpinionTracker()
tracker.track_from_messages(state)

# 3. Analyze opinion changes
analyzer = OpinionEvolutionAnalyzer()
report = analyzer.generate_evolution_report(state)
print("Overall Trend:", report["overall_trend"])
print("Total Shifts Detected:", report["total_shifts_detected"])

# 4. Save to disk and export for Week 4
store = DiscussionStore()
store.save(state)
store.export_for_week4(state)
```

If an agent performs mid-discussion retrieval, log it into state:
```python
state.record_retrieval(
    agent_id="knowledge_base_analyst",
    round_number=2,
    query="Mexico vs South Africa 2010 stats",
    evidence=["Tshabalala 55' goal, Marquez 79' equalizer"],
    tool_name="get_knowledge"
)
```
The store will automatically include it when saving to disk and exporting for Week 4.
