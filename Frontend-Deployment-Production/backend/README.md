# Backend API Architecture (FastAPI)

This directory contains the production-ready FastAPI backend for the Multi-Agent Collaboration project. It acts as the bridge between the Frontend UI and the underlying AI modules (Weeks 1-4).

## 🏗️ Architecture & Integration Strategy

A major requirement for this backend was to **directly integrate** with the ML pipelines from Week 3 and Week 4, rather than using stubs or duplicating code.

### The Sibling-Repo Import Pattern
Because both the `Multi-Agent-Collaboration` (Week 3) and `Analytics-Intelligence-Layer` (Week 4) repositories use `src` as their top-level package, a naive `sys.path.append()` causes namespace collisions.

To solve this, the backend uses a custom Context Manager (`_week3_context` and `_week4_context`) in the `services/` layer:
1. It temporarily removes the current `src` modules from `sys.modules`.
2. Injects the sibling repository's path to `sys.path`.
3. Executes the multi-agent logic so that any internal lazy imports (e.g., `LLMJudgeExtractor` calling Week 2 agents) resolve correctly.
4. Cleans up and restores the original module state.

This ensures zero-copy code reuse from previous weeks.

---

## 📡 API Endpoints

All data contracts (Requests/Responses) are strictly validated using **Pydantic** models (found in `schemas/models.py`).

### 1. `GET /health`
- **Purpose:** Lightweight liveness probe for deployment checks.
- **Returns:** HTTP 200 `{"status": "ok"}`
- **Notes:** Executes in < 5ms. Makes zero DB or LLM calls.

### 2. `GET /topics`
- **Purpose:** Fetches the pre-configured discussion topics.
- **Returns:** List of strings (e.g., `["France vs England — 2026 World Cup Third Place", ...]`).
- **Notes:** Reads directly from Week 3's `MATCH_REGISTRY` without invoking the LLM.

### 3. `POST /discussions`
- **Purpose:** Starts a full multi-round agent discussion.
- **Payload:** `{"topic": "Your topic here"}`
- **Returns:** `discussion_id`, status, participating agents, and number of rounds.
- **Notes:** Synchronous execution. Automatically detects the best persona set, builds the agent ring-graph, runs 3 rounds, tracks opinions, and exports data for Week 4.

### 4. `GET /discussions/{discussion_id}`
- **Purpose:** Retrieves the chat history of a completed discussion.
- **Returns:** All rounds, agent messages, timestamps, and termination reasons.
- **Notes:** Loads the state directly from Week 3's `data/discussions/` storage.

### 5. `GET /discussions/{discussion_id}/analytics`
- **Purpose:** Computes advanced metrics on a finished discussion.
- **Returns:** 
  - `opinion_change`: Pre/post stance differences.
  - `agreement`: Convergence scores per round.
  - `influence`: Which agent swayed others the most.
  - `sentiment`: LLM-based sentiment scoring per message.
- **Notes:** Invokes Week 4's analytics engine on the exported discussion data.

### 6. `POST /retrieval/search` (Original Contributor Docs)
- **Purpose:** Directly interacts with the Retrieval Integration from Week 1.
- **Notes:** `backend/integrations/week1_retrieval/` is the only place that imports Week 1/2 code. `backend/routers/retrieval.py` calls it and exposes a plain HTTP contract (`schemas/retrieval.py`).
- **Isolated Testing:** To try it live before it's wired into the full app, you can run a tiny FastAPI app:
  ```python
  from fastapi import FastAPI
  from backend.routers.retrieval import router
  app = FastAPI()
  app.include_router(router)
  ```
  Then run `uvicorn <that file>:app --reload` and POST to `/retrieval/search`.

---

## 📁 Directory Structure

```text
backend/
├── main.py                # FastAPI app entry point & exception handlers
├── logging_config.py      # Standardized request/response logging
├── routers/               # HTTP Route controllers (health, topics, discussions, retrieval)
├── schemas/               # Pydantic models (models.py, retrieval.py)
├── services/              # Business logic & sibling-repo integrations (week3_client.py)
├── integrations/          # Week 1 retrieval integration client
└── tests/                 # Pytest suite with monkeypatched external calls
```

## 🧪 Testing

The backend includes a comprehensive acceptance test suite using `pytest` and FastAPI's `TestClient`.

The tests are designed to run **instantly** and **without external dependencies** by monkeypatching the Week 3 and Week 4 integration services. This means no LLM API calls are made during tests.

Run tests via:
```bash
python -m pytest backend/tests/ -v
```
