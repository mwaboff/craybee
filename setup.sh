#!/usr/bin/env bash
# One-time contributor setup. Safe to re-run after a git pull.
set -euo pipefail

cd "$(dirname "$0")"

command -v uv >/dev/null 2>&1 || {
  echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
}
command -v node >/dev/null 2>&1 || {
  echo "Node 20+ is required for frontend development: https://nodejs.org/" >&2
  exit 1
}

echo "==> Python dependencies"
uv sync

echo "==> Frontend dependencies"
(cd frontend && npm ci)

echo "==> Building frontend"
(cd frontend && npm run build)
rm -rf backend/static
cp -r frontend/dist backend/static

cat <<'MSG'

Setup complete.

  uv run craybee dev      hot reload, browser on :5173  (needs Node)
  uv run craybee serve    the built app, single process (no Node)
  uv run craybee build    recompile backend/static/

MSG
