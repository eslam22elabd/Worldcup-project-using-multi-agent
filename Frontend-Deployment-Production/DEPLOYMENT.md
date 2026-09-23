# Production Deployment & Operations Guide

This guide outlines how to configure, containerize, run, and deploy the **Qubeterra Multi-Agent Discussion & Analytics Platform** (Week 5 final product).

---

## 📋 Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Environment Configuration](#environment-configuration)
3. [Local Development](#local-development)
4. [Docker Containerization](#docker-containerization)
5. [Cloud Deployment Options](#cloud-deployment-options)
6. [Liveness & Health Verification](#liveness--health-verification)
7. [Troubleshooting Guide](#troubleshooting-guide)

---

## 🏗 Architecture Overview

The system is packaged as a unified, production-ready stack:

```text
┌─────────────────────────────────────────────────────────────┐
│                    Container / Host                         │
│                                                             │
│  ┌────────────────────────┐      ┌───────────────────────┐  │
│  │   React + Vite SPA     │ ───> │  FastAPI Backend      │  │
│  │   (Discussion &        │ HTTP │  Port 8000            │  │
│  │    Analytics Views)    │      │  • /health            │  │
│  └────────────────────────┘      │  • /topics            │  │
│                                  │  • /discussions       │  │
│                                  │  • /discussions/{id}  │  │
│                                  │  • /analytics         │  │
│                                  │  • /retrieval/search  │  │
│                                  └───────────┬───────────┘  │
│                                              │              │
│                       ┌──────────────────────┼──────────┐   │
│                       ▼                      ▼          ▼   │
│                 Week 1 RAG             Week 3 Engine  Week 4│
│                 (Retrieval)             (Discussion) (Analytics)
└─────────────────────────────────────────────────────────────┘
```

* **Frontend**: React 18, Vite, responsive CSS dashboard.
* **Backend**: FastAPI, Uvicorn, Pydantic schemas, structured logging.
* **Production Serving**: In Docker / production, FastAPI mounts the built `frontend/dist` directory at root (`/`), providing a single-port (`8000`) application with zero CORS friction.

---

## ⚙️ Environment Configuration

Copy the sample environment file:

```bash
cp .env.example .env
```

| Variable | Required? | Default | Description |
| :--- | :---: | :---: | :--- |
| `OPENROUTER_API_KEY` | Optional* | None | Required to run live LLM agents and sentiment. Not required when inspecting existing/sample runs. |
| `PORT` | Optional | `8000` | Port for the HTTP server. |
| `VITE_API_BASE_URL` | Optional | `http://localhost:8000` | Backend API URL for the frontend. |
| `WEEK3_PROJECT_PATH` | Optional | Auto-detected | Path to the `Multi-Agent-Collaboration` repository. |
| `WEEK4_PROJECT_PATH` | Optional | Auto-detected | Path to the `Analytics-Intelligence-Layer` repository. |

---

## 💻 Local Development

### 1. Backend

```bash
# From repository root
pip install -r backend/requirements.txt

# Start backend server
python -m uvicorn backend.main:app --reload --port 8000
```

* API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
* Health check: [http://localhost:8000/health](http://localhost:8000/health)

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

* Frontend Dev Server: [http://localhost:5173](http://localhost:5173)

### 3. Run Tests

```bash
# Run all backend unit & integration tests
python -m pytest backend/tests/ -v
```

---

## 🐳 Docker Containerization

The repository provides a multi-stage `Dockerfile` that compiles the React frontend and packages it with the FastAPI backend into a lean Python 3.11 image.

### Building the Docker Image

```bash
docker build -t opinion-platform .
```

### Running the Container

```bash
docker run -d -p 8000:8000 --name opinion-platform --env-file .env opinion-platform
```

Once running, access the complete application at:
👉 **http://localhost:8000**

### Using Docker Compose

Alternatively, use Docker Compose:

```bash
# Build and launch
docker compose up --build -d

# View logs
docker compose logs -f

# Stop container
docker compose down
```

---

## ☁️ Cloud Deployment Options

The containerized application can be deployed to any cloud container service:

### Option A: Render (Recommended for Free Tier)
1. Push your repository to GitHub.
2. In Render Dashboard, click **New +** -> **Web Service**.
3. Select your repository.
4. Choose **Docker** runtime (Render automatically detects the root `Dockerfile`).
5. Set environment variables (`PORT=8000`, `OPENROUTER_API_KEY=...`).
6. Click **Deploy Web Service**.
7. Your app is live at `https://<service-name>.onrender.com`.

### Option B: Railway
1. Click **New Project** -> **Deploy from GitHub repo**.
2. Railway detects the `Dockerfile` and builds both stages.
3. Add variable `PORT=8000` in the Settings tab.
4. Generate a public domain under **Networking**.

### Option C: Hugging Face Spaces (Docker Space)
1. Create a new Space on Hugging Face, selecting **Docker** as the SDK.
2. Push this repository as the remote origin.
3. Hugging Face automatically runs the `Dockerfile` on port 7860 (set `ENV PORT=7860` or map accordingly).

---

## 🩺 Liveness & Health Verification

Verify that the deployed service is active and responsive:

```bash
curl -I http://localhost:8000/health
```

Expected response:
```http
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok"}
```

---

## 🛠 Troubleshooting Guide

### 1. Port 8000 is already in use
**Symptom:** `ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)`  
**Solution:** Either stop the conflicting process or change the port:
```bash
python -m uvicorn backend.main:app --port 8080
```

### 2. Frontend cannot reach backend (CORS or Network Error)
**Symptom:** `Failed to load discussion (TypeError: Failed to fetch)`  
**Solution:**
- Verify backend is running: `curl http://localhost:8000/health`.
- In development, ensure `VITE_API_BASE_URL` matches your backend URL.
- In Docker/Production, the frontend is served from the same origin as the backend (`/`), eliminating CORS errors entirely.

### 3. OpenRouter API Key Missing
**Symptom:** `discussion_failed: OPENROUTER_API_KEY not set`  
**Solution:** Set your API key in `.env` or click **"Load Pre-Recorded 3-Round Discussion & Analytics"** in the UI to explore full discussion and analytics capabilities without making live LLM calls.

### 4. Sibling Repository Path Not Found
**Symptom:** `ImportError` or `ModuleNotFoundError` when calling analytics.  
**Solution:** The backend auto-resolves sibling and nested layouts. If your repository folder structure differs, explicitly specify:
```bash
export WEEK3_PROJECT_PATH="/absolute/path/to/Multi-Agent-Collaboration"
export WEEK4_PROJECT_PATH="/absolute/path/to/Analytics-Intelligence-Layer"
```
