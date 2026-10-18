#!/usr/bin/env bash
# Portable authoring checks: no Xcode, Swift publisher, signing key or GitHub credentials.
set -euo pipefail
TASK_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$TASK_ROOT"
command -v bun >/dev/null || { echo 'Install the Bun version in .bun-version first' >&2; exit 1; }
TASK_BUN_VERSION=$(cat .bun-version)
[[ "$(bun --version)" == "$TASK_BUN_VERSION" ]] || { echo "Use pinned Bun $TASK_BUN_VERSION (see .bun-version)" >&2; exit 1; }
test -d node_modules/typescript || { echo 'Run bun install --frozen-lockfile --ignore-scripts before authoring checks' >&2; exit 1; }
command -v openssl >/dev/null || { echo 'OpenSSL is required for the HTTPS fixture tests' >&2; exit 1; }
TASK_TEMP=$(mktemp -d /tmp/interceptor-authoring-check.XXXXXX)
trap 'rm -rf -- "$TASK_TEMP"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tools/tests -v
python3 tools/build.py --root "$TASK_ROOT" --output "$TASK_TEMP/site"
python3 tools/build.py --root "$TASK_ROOT" --output "$TASK_TEMP/repro"
diff -qr "$TASK_TEMP/site/plugins" "$TASK_TEMP/repro/plugins"
echo 'Portable authoring, generation and HTTPS checks passed. Run tools/check.sh on macOS for native QuickJS and signature verification.'
