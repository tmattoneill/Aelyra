#!/usr/bin/env bash
#
# Aelyra production launcher.
#
# Serves plain HTTP on the loopback interface by design: nginx terminates TLS
# in front of it with the real certificate for the public hostname. The certs/
# directory holds an mkcert certificate valid only for localhost, so serving it
# directly to browsers would fail verification. Set SSL_CERTFILE and
# SSL_KEYFILE to have uvicorn terminate TLS itself.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env.prod ]; then
    echo "❌ .env.prod not found." >&2
    exit 1
fi

# `set -a` exports everything sourced, and sourcing handles quoting and spaces
# correctly. The previous `export $(cat .env.prod | xargs)` split values on
# whitespace and exposed every secret in the process table.
set -a
# shellcheck disable=SC1091
source .env.prod
set +a

# The deploy creates .venv on the remote; local development uses venv.
for candidate in .venv venv; do
    if [ -f "$candidate/bin/activate" ]; then
        # shellcheck disable=SC1090
        source "$candidate/bin/activate"
        echo "📦 Using $candidate"
        break
    fi
done

if ! command -v uvicorn >/dev/null 2>&1; then
    echo "❌ uvicorn not found. Create the virtualenv and install requirements.txt first." >&2
    exit 1
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

SSL_ARGS=()
if [ -n "${SSL_CERTFILE:-}" ] && [ -n "${SSL_KEYFILE:-}" ]; then
    SSL_ARGS=(--ssl-certfile="$SSL_CERTFILE" --ssl-keyfile="$SSL_KEYFILE")
    echo "🔐 Terminating TLS in the app"
fi

echo "🚀 Starting Aelyra on ${HOST}:${PORT}"

# Single worker is required, not a preference: OAuth state and the pending auth
# codes live in process memory, so a second worker would reject callbacks it
# did not issue.
exec uvicorn main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips='127.0.0.1' \
    "${SSL_ARGS[@]}"
