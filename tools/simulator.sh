#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
bash "$TASK_ROOT/tools/build-runtime.sh" >&2
exec "$TASK_ROOT/.tools/bin/interceptor-simulator" "$@"
