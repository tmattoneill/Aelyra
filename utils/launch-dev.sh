#!/usr/bin/env bash
#
# Starts the backend and frontend development servers together.
# Ctrl+C stops both.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env ]; then
    echo "❌ .env not found. Copy .env.example to .env and fill in your API keys." >&2
    exit 1
fi

if [ -f venv/bin/activate ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
else
    echo "⚠️  No venv found. Create one with: uv venv --python 3.12 venv" >&2
fi

if [ ! -d frontend/node_modules ]; then
    echo "📦 Installing frontend dependencies..."
    (cd frontend && npm install)
fi

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "🐍 Starting backend on http://127.0.0.1:5988"
python main.py &
BACKEND_PID=$!

# Poll the health endpoint rather than sleeping a fixed two seconds and hoping.
printf "   waiting for backend"
for _ in $(seq 1 30); do
    if curl -fsS --max-time 1 http://127.0.0.1:5988/health >/dev/null 2>&1; then
        echo " ready"
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo ""
        echo "❌ Backend exited during startup. Check the output above." >&2
        exit 1
    fi
    printf "."
    sleep 1
done

echo "⚛️  Starting frontend on http://localhost:3000"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "✅ Running. Press Ctrl+C to stop both."
echo "   Backend:  http://127.0.0.1:5988"
echo "   Frontend: http://localhost:3000"
echo ""

wait
