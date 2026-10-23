#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$TASK_ROOT"
test -f biome-plugins/no-let.grit || {
    echo 'Initialize lint rules with git submodule update --init biome-plugins' >&2
    exit 1
}
bun node_modules/@biomejs/biome/bin/biome lint --error-on-warnings .
