#!/usr/bin/env bash
#
# Aelyra production deployment.
# Builds the frontend, syncs the tree to the production host, migrates, restarts.
#
# Server details live in .deploy.env (gitignored) so they stay out of the public
# repo. Copy .deploy.env.example to .deploy.env and fill it in.
#
# Usage:
#   ./utils/deploy-prod.sh            deploy
#   ./utils/deploy-prod.sh --dry-run  show what rsync would transfer, change nothing

set -euo pipefail

# Always operate from the repo root, whatever directory the script was invoked from.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=""
case "${1:-}" in
    --dry-run) DRY_RUN="--dry-run"; echo "🔍 DRY RUN — no files will be changed" ;;
    "")        ;;
    *)         echo "Unknown argument: $1 (expected --dry-run or nothing)" >&2; exit 2 ;;
esac

if [ ! -f .deploy.env ]; then
    echo "❌ .deploy.env not found. Copy .deploy.env.example and fill in your server details." >&2
    exit 1
fi
set -a; source .deploy.env; set +a

# Fail loudly on missing config rather than rsyncing --delete somewhere unintended.
: "${REMOTE_USER:?REMOTE_USER must be set in .deploy.env}"
: "${REMOTE_HOST:?REMOTE_HOST must be set in .deploy.env}"
: "${REMOTE_PORT:?REMOTE_PORT must be set in .deploy.env}"
: "${REMOTE_PATH:?REMOTE_PATH must be set in .deploy.env}"
: "${REMOTE_RESTART_CMD:?REMOTE_RESTART_CMD must be set in .deploy.env}"

# rsync --delete against a bare home directory would wipe unrelated files.
case "$REMOTE_PATH" in
    ""|"~"|"~/"|"/"|"/home"|"/home/"*/)
        echo "❌ Refusing to deploy: REMOTE_PATH='$REMOTE_PATH' is too broad for rsync --delete." >&2
        exit 1 ;;
esac

if [ ! -f .env.prod ]; then
    echo "❌ .env.prod not found — the remote needs it to boot." >&2
    exit 1
fi

echo "🚀 Deploying Aelyra to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"
echo ""

# Frontend build. npm ci honours package-lock.json for a reproducible tree.
echo "⚛️  Building frontend..."
( cd frontend && npm ci && npm run build )

echo ""
echo "📤 Syncing to remote..."
rsync -avz --delete ${DRY_RUN} \
    --exclude '.git' \
    --exclude '.env*' \
    --exclude '.deploy.env' \
    --exclude 'venv' \
    --exclude '.venv' \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache' \
    --exclude '*.db' \
    --exclude 'certs' \
    --exclude 'logs' \
    --exclude '.DS_Store' \
    --exclude '.idea' \
    --exclude '.claude' \
    --exclude '.devctx' \
    --exclude 'wireframes' \
    -e "ssh -p ${REMOTE_PORT}" \
    ./ "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/"

if [ -n "$DRY_RUN" ]; then
    echo ""
    echo "🔍 Dry run complete. Nothing was changed."
    exit 0
fi

echo ""
echo "🔒 Setting permissions for nginx..."
ssh -p "${REMOTE_PORT}" "${REMOTE_USER}@${REMOTE_HOST}" \
    "chmod 755 ${REMOTE_PATH} ${REMOTE_PATH}/frontend ${REMOTE_PATH}/frontend/dist && chmod -R a+rX ${REMOTE_PATH}/frontend/dist"

echo ""
echo "📦 Installing dependencies and migrating on remote..."
ssh -p "${REMOTE_PORT}" "${REMOTE_USER}@${REMOTE_HOST}" \
    "cd ${REMOTE_PATH} && source .venv/bin/activate && pip install -r requirements.txt && alembic upgrade head"

echo ""
echo "🔄 Restarting service..."
ssh -p "${REMOTE_PORT}" "${REMOTE_USER}@${REMOTE_HOST}" "${REMOTE_RESTART_CMD}"

echo ""
echo "🩺 Health check..."
if ssh -p "${REMOTE_PORT}" "${REMOTE_USER}@${REMOTE_HOST}" \
    "curl -fsS --max-time 10 http://127.0.0.1:\${PORT:-8000}/health" >/dev/null 2>&1; then
    echo "✅ Deployment complete and service is healthy."
else
    echo "⚠️  Deployed, but the health check did not pass. Check the service logs." >&2
    exit 1
fi
