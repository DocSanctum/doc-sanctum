#!/usr/bin/env bash
# Start doc-sanctum via docker compose.
# Auto-rebuilds images when the current commit differs from the last
# commit this script built at (e.g. after `git pull`). Pass --build to
# force a rebuild regardless.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

STATE_FILE=".docker_last_build"
FORCE_BUILD=false

for arg in "$@"; do
  case "$arg" in
    --build)
      FORCE_BUILD=true
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: $0 [--build]" >&2
      exit 1
      ;;
  esac
done

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
elif [ -n "$CURRENT_COMMIT" ]; then
  if [ ! -f "$STATE_FILE" ] || [ "$(cat "$STATE_FILE")" != "$CURRENT_COMMIT" ]; then
    NEED_BUILD=true
  fi
fi

if $NEED_BUILD; then
  echo "Changes detected, rebuilding images..."
  docker compose up -d --build
else
  echo "No changes detected, starting with existing images. (force rebuild: $0 --build)"
  docker compose up -d
fi

if [ -n "$CURRENT_COMMIT" ]; then
  echo "$CURRENT_COMMIT" > "$STATE_FILE"
fi

echo ""
echo "doc-sanctum is up."
echo "  Frontend: http://localhost:${FRONTEND_PORT:-3000}"
echo "  Backend API: http://localhost:${BACKEND_PORT:-8000}"
echo ""
echo "View logs: docker compose logs -f"
echo "Stop: ./stop.sh"
