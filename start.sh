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
      echo "알 수 없는 옵션: $arg" >&2
      echo "사용법: $0 [--build]" >&2
      exit 1
      ;;
  esac
done

if [ ! -f .env ]; then
  echo ".env 파일이 없습니다. .env.example을 참고하여 .env를 먼저 만들어주세요:"
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
  echo "변경 사항이 감지되어 이미지를 다시 빌드합니다..."
  docker compose up -d --build
else
  echo "변경 사항이 없어 기존 이미지로 바로 실행합니다. (강제 재빌드: $0 --build)"
  docker compose up -d
fi

if [ -n "$CURRENT_COMMIT" ]; then
  echo "$CURRENT_COMMIT" > "$STATE_FILE"
fi

echo ""
echo "doc-sanctum이 시작되었습니다."
echo "  프론트엔드: http://localhost:${FRONTEND_PORT:-3000}"
echo "  백엔드 API: http://localhost:${BACKEND_PORT:-8000}"
echo ""
echo "로그 보기: docker compose logs -f"
echo "중지하기: ./stop.sh"
