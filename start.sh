#!/usr/bin/env bash
# Start doc-sanctum via docker compose.
# Auto-rebuilds images when the current commit differs from the last
# commit this script built at (e.g. after `git pull`), or when switching
# between dev/prod mode. Pass --build to force a rebuild regardless.
#
# Dev (default): docker-compose.yml + docker-compose.override.yml
#   (auto-merged by docker compose) — Vite dev server, backend auto-reload.
# Prod (--prod): docker-compose.yml + docker-compose.prod.yml
#   (nginx-served prebuilt frontend, no backend auto-reload).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

STATE_FILE=".docker_last_build"
MODE_STATE_FILE=".docker_last_mode"
FORCE_BUILD=false
PROD=false

for arg in "$@"; do
  case "$arg" in
    --build)
      FORCE_BUILD=true
      ;;
    --prod)
      PROD=true
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: $0 [--build] [--prod]" >&2
      exit 1
      ;;
  esac
done

CURRENT_MODE="dev"
COMPOSE=(docker compose)
if $PROD; then
  CURRENT_MODE="prod"
  COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
fi

if [ ! -f .env ]; then
  echo ".env file not found. Create one from .env.example first:"
  echo "  cp .env.example .env"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

CURRENT_COMMIT=""
if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
  CURRENT_COMMIT=$(git rev-parse HEAD)
fi

NEED_BUILD=false
if $FORCE_BUILD; then
  NEED_BUILD=true
elif [ ! -f "$MODE_STATE_FILE" ] || [ "$(cat "$MODE_STATE_FILE")" != "$CURRENT_MODE" ]; then
  # Switching dev <-> prod changes the frontend's build target; without a
  # rebuild, `up` would reuse the previously built image for the old target.
  NEED_BUILD=true
elif [ -n "$CURRENT_COMMIT" ]; then
  if [ ! -f "$STATE_FILE" ] || [ "$(cat "$STATE_FILE")" != "$CURRENT_COMMIT" ]; then
    NEED_BUILD=true
  fi
fi

if $NEED_BUILD; then
  echo "Changes detected, rebuilding images..."
  "${COMPOSE[@]}" up -d --build
else
  echo "No changes detected, starting with existing images. (force rebuild: $0 --build)"
  "${COMPOSE[@]}" up -d
fi

echo "$CURRENT_MODE" > "$MODE_STATE_FILE"
if [ -n "$CURRENT_COMMIT" ]; then
  echo "$CURRENT_COMMIT" > "$STATE_FILE"
fi

echo ""
echo "doc-sanctum is up ($CURRENT_MODE mode)."
echo "  Frontend: http://localhost:${FRONTEND_PORT:-3000}"
echo "  Backend API: http://localhost:${BACKEND_PORT:-8000}"
echo ""
echo "View logs: docker compose logs -f"
echo "Stop: ./stop.sh"
