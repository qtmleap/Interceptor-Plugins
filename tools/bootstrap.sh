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
if [[ -e "$TASK_SOURCE" ]]; then
    [[ ! -L "$TASK_SOURCE" && -d "$TASK_SOURCE/.git" ]] || { echo 'upstream cache is not a Git checkout' >&2; exit 1; }
else
    mkdir -p "$TASK_ROOT/.tools"
    git init -q -b codex/upstream-cache "$TASK_SOURCE"
    git -C "$TASK_SOURCE" remote add origin https://github.com/qtmleap/Interceptor.git
    git -C "$TASK_SOURCE" fetch --depth 1 --no-tags origin "$TASK_PIN"
    git -C "$TASK_SOURCE" sparse-checkout set Packages/InterceptorAutomation
    git -C "$TASK_SOURCE" -c advice.detachedHead=false checkout --detach "$TASK_PIN"
fi
# Apply the same provenance/input checks after a new checkout and cache reuse.
[[ "$(git -C "$TASK_SOURCE" remote get-url origin)" == 'https://github.com/qtmleap/Interceptor.git' ]] || { echo 'upstream remote mismatch' >&2; exit 1; }
[[ "$(git -C "$TASK_SOURCE" rev-parse HEAD)" == "$TASK_PIN" ]] || { echo 'upstream cache pin mismatch; preserve and inspect it' >&2; exit 1; }
python3 - "$TASK_SOURCE" <<'PYTHON'
import os, stat, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args])
if git('status', '--porcelain', '--untracked-files=no'):
    raise SystemExit('upstream cache has modified source; preserve and inspect it')
# Ignored files are inputs too: SwiftPM includes extra sources even if Git's
# ignore rules hide them. Check every path, including out-of-cone sparse paths.
extra = set()
for flags in (('--others', '--exclude-standard'), ('--others', '--ignored', '--exclude-standard')):
    extra.update(path for path in git('ls-files', '-z', *flags).split(b'\0') if path)
build = root / 'Packages/InterceptorAutomation/.build'
allowed_prefix = b'Packages/InterceptorAutomation/.build/'
if any(not path.startswith(allowed_prefix) for path in extra):
    raise SystemExit('upstream cache has unexpected non-build inputs; preserve and inspect it')
if extra:
    info = build.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise SystemExit('upstream cache has an unexpected SwiftPM build directory; preserve and inspect it')
PYTHON
mkdir -p "$TASK_ROOT/build/evidence"
{
    git -C "$TASK_SOURCE" rev-parse HEAD
    bun --version
    python3 --version
    uname -s
    cargo --version
    rustc --version
    cc --version
} > "$TASK_ROOT/build/evidence/toolchain.txt"
