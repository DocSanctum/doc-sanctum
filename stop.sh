#!/usr/bin/env bash
# Stop doc-sanctum's docker compose services.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

docker compose down

echo "doc-sanctum이 중지되었습니다."
