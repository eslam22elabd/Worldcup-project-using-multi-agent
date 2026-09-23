#!/usr/bin/env bash
# ==============================================================================
# build.sh — Railway build script (Python + Node in one)
# Runs during Railway's build phase:
#   1. Install Node.js 20 (Railway Python image doesn't include npm)
#   2. Install Python dependencies
#   3. Build React frontend (output → frontend/dist)
# ==============================================================================
set -e  # Exit immediately on error

# ── Install Node.js 20 via NodeSource ──────────────────────────────────────
if ! command -v npm &> /dev/null; then
    echo "==> Node.js not found. Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
    echo "==> Node.js $(node --version) / npm $(npm --version) installed."
else
    echo "==> npm already available: $(npm --version)"
fi

# ── Install Python dependencies ────────────────────────────────────────────
echo "==> Installing Python dependencies..."
pip install -r backend/requirements.txt

# ── Build React frontend ───────────────────────────────────────────────────
echo "==> Installing Node dependencies and building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "==> Build complete. frontend/dist is ready."
