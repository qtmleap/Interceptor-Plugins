#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TASK_SOURCE="$TASK_ROOT/.tools/interceptor"
TASK_PIN=$(python3 - "$TASK_ROOT/repository-config.json" <<'PY'
import json, re, sys
pin = json.load(open(sys.argv[1]))['upstreamRevision']
if not isinstance(pin, str) or not re.fullmatch(r'[0-9a-f]{40}', pin):
    raise SystemExit('invalid upstreamRevision')
print(pin)
PY
)
command -v swift >/dev/null
python3 - <<'PY'
import re, subprocess
result = subprocess.run(['swift', '--version'], capture_output=True, text=True)
match = re.search(r'\bSwift version (\d+)\.(\d+)', result.stdout + result.stderr, re.I)
if result.returncode or not match or tuple(map(int, match.groups())) < (6, 4):
    raise SystemExit('Repository checks require Swift 6.4 or later; select Xcode 27.0.')
PY
if [[ -e "$TASK_SOURCE" ]]; then
    [[ -d "$TASK_SOURCE/.git" ]] || { echo 'upstream cache is not a Git checkout' >&2; exit 1; }
    [[ "$(git -C "$TASK_SOURCE" remote get-url origin)" == 'https://github.com/qtmleap/Interceptor.git' ]] || { echo 'upstream remote mismatch' >&2; exit 1; }
    [[ "$(git -C "$TASK_SOURCE" rev-parse HEAD)" == "$TASK_PIN" ]] || { echo 'upstream cache pin mismatch; preserve and inspect it' >&2; exit 1; }
    [[ -z "$(git -C "$TASK_SOURCE" status --porcelain --untracked-files=no)" ]] || { echo 'upstream cache has modified source' >&2; exit 1; }
else
    mkdir -p "$TASK_ROOT/.tools"
    git init -q -b codex/upstream-cache "$TASK_SOURCE"
    git -C "$TASK_SOURCE" remote add origin https://github.com/qtmleap/Interceptor.git
    git -C "$TASK_SOURCE" fetch --depth 1 --no-tags origin "$TASK_PIN"
    git -C "$TASK_SOURCE" sparse-checkout set Packages/InterceptorAutomation
    git -C "$TASK_SOURCE" -c advice.detachedHead=false checkout --detach "$TASK_PIN"
fi
[[ "$(git -C "$TASK_SOURCE" rev-parse HEAD)" == "$TASK_PIN" ]]
mkdir -p "$TASK_ROOT/build/evidence"
{
    git -C "$TASK_SOURCE" rev-parse HEAD
    swift --version
    xcodebuild -version
} > "$TASK_ROOT/build/evidence/toolchain.txt"
