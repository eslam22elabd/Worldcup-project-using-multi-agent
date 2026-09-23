# Qubeterra Multi-Agent Collaboration & Production Deployment (Week 5)

[![Backend Tests](https://img.shields.io/badge/pytest-22%20passed-brightgreen.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-009688.svg)]()
[![React](https://img.shields.io/badge/React-18-61dafb.svg)]()
[![Docker](https://img.shields.io/badge/Docker-Multi--stage-2496ed.svg)]()

This repository contains the **production-ready web application** bringing together all components developed throughout Weeks 1 through 4 into a unified, containerized, and deployable product.

---

## 🌟 End-to-End System Architecture

```text
                                  USER
                                    │
                                    ▼
                         ┌────────────────────┐
                         │   Web Frontend     │
                         │ (Topic / Replay /  │
                         │  Analytics View)   │
                         └─────────┬──────────┘
                                   │ HTTP
                                   ▼
                         ┌────────────────────┐
                         │    FastAPI Core    │
                         │    (Port 8000)     │
                         │ • /health          │
                         │ • /topics          │
                         │ • /discussions     │
                         │ • /analytics       │
                         │ • /retrieval/search│
                         └─────────┬──────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
        Week 1 RAG          Week 3 Engine        Week 4 Engine
      (Knowledge Base)    (Multi-Agent Debate)    (Analytics)
              │                    │                    │
              └────────────────────┴────────────────────┘
                                   │
                                   ▼
                            Data & Exports
```

---

## 🚀 Key Features

* **Domain & Topic Selection (Week 3 / 5)**: Select from pre-configured World Cup discussion topics or enter custom match queries in Arabic or English.
* **Discussion Interface (Weeks 2–3)**: Displays multi-round agent interactions, agent personas, message history, timestamps, and reasoning. Supports both real-time execution and instant 3-round replay mode.
* **Analytics Dashboard (Week 4)**:
  * **Opinion Trajectory**: Stance progression across rounds for each agent (-1.00 to +1.00).
  * **Group Agreement**: Round-by-round consensus and convergence metrics.
  * **Influence Rankings**: Quantification of which agent swayed peer stances most effectively.
  * **Sentiment & Arguments**: Lexical and model-evaluated polarity plus key extracted arguments.
  * **Interaction Graph**: Node-and-edge communication topology showing agent interaction networks.
* **Week 1 RAG Integration**: Search domain documents directly via `/retrieval/search` or the built-in UI search bar.
* **Unified Single-Port Deployment**: FastAPI serves API routes while serving the built React single-page app from `/`.
* **Zero-External Test Suite**: Instant test suite with 22 passing tests.

---

## 📋 Reviewer Reproduction Guide

Follow these exact steps to reproduce and verify the application locally or in Docker.

### 1. Prerequisites
* Python 3.10+
* Node.js 18+ and `npm`
* Docker (optional for containerized run)

### 2. Environment Setup
```bash
cp .env.example .env
```

### 3. Running Backend Tests
```bash
python -m pytest backend/tests/ -v
```
*Expected: 22 passed in < 1 second.*

### 4. Running the Application Locally

#### Option A: Running Development Servers
```bash
# Terminal 1: Backend
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```
* Backend API & Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
* Frontend: [http://localhost:5173](http://localhost:5173)

#### Option B: Building & Running Unified Static Mode
```bash
# Build React app
cd frontend && npm install && npm run build && cd ..

# Run FastAPI (automatically mounts and serves frontend at /)
python -m uvicorn backend.main:app --port 8000
```
Open [http://localhost:8000](http://localhost:8000) to view the complete integrated application.

---

## 🐳 Docker Containerization

The multi-stage `Dockerfile` handles building the React frontend and packaging it into a slim Python 3.11 image.

### 1. Build Docker Image
```bash
docker build -t opinion-platform .
```

### 2. Run Container
```bash
docker run -p 8000:8000 opinion-platform
```

### 3. Verify Health Check
```bash
curl http://localhost:8000/health
```
*Output: `{"status": "ok"}`*

Access the application in your browser:
👉 **http://localhost:8000**

Or using Docker Compose:
```bash
docker compose up --build -d
```

---

## 🌐 Public Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for full instructions on deploying to free cloud providers (Render, Railway, Hugging Face Spaces, GitHub Codespaces).

---

## 📡 API Reference & Endpoints

| Method | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Lightweight liveness probe (`{"status": "ok"}`). |
| `GET` | `/topics` | Returns available discussion topics. |
| `POST` | `/discussions` | Starts a multi-round agent discussion (synchronous). |
| `GET` | `/discussions/{id}` | Retrieves full round and message history for a discussion. |
| `GET` | `/discussions/{id}/analytics` | Computes/returns opinion trajectory, agreement, influence, sentiment, and interaction graph. |
| `POST` | `/retrieval/search` | Direct Week 1 RAG query endpoint returning relevant sources. |

Interactive OpenAPI documentation is available at `/docs`.

---

## 🧪 Definition of Done Checklist

- [x] **Frontend**: Runs locally, provides topic selection, multi-round discussion view, and full analytics dashboard.
- [x] **Backend**: Unified FastAPI API integrating Weeks 1, 3, and 4.
- [x] **Discussion**: Displays at least 3 rounds, distinct agent personas, and full message logs.
- [x] **Analytics**: Surfacing Opinion Trajectory, Agreement, Influence, Sentiment, and Interaction Graph.
- [x] **Containerization**: Multi-stage `Dockerfile` and `docker-compose.yml` build and run cleanly.
- [x] **Health Check**: `GET /health` returns HTTP 200 with status payload.
- [x] **Logging**: Structured request, response, duration, and error logging.
- [x] **Documentation**: Reproduction commands, `DEPLOYMENT.md`, `.env.example`, and troubleshooting guide.
