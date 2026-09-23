#!/usr/bin/env bash
# ==============================================================================
# build.sh — Render build script (no Docker)
# Runs during Render's build phase:
#   1. Install Python dependencies
#   2. Build React frontend (output → frontend/dist)
# ==============================================================================
set -e  # Exit immediately on error

echo "==> Installing Python dependencies..."
pip install -r backend/requirements.txt

echo "==> Installing Node dependencies and building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "==> Build complete. frontend/dist is ready."
