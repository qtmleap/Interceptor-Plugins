#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$TASK_ROOT"
: "${GITHUB_REPOSITORY:?use the configured GitHub repository}"
: "${GITHUB_REF:?use refs/heads/main}"
python3 tools/guard.py --root "$TASK_ROOT" --repository "$GITHUB_REPOSITORY" --ref "$GITHUB_REF"
: "${INTERCEPTOR_SIGNING_KEY_PATH:?a key outside the checkout is required}"
TASK_REMOTE_HEAD=$(gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/main" --jq .object.sha)
[[ "$(git rev-parse HEAD)" == "$TASK_REMOTE_HEAD" ]] || { echo 'stale main: refusing publication' >&2; exit 1; }
TASK_VERIFIER="$(swift build --package-path tools/Verifier --configuration release --show-bin-path)/interceptor-samples-check"
TASK_PUBLISHER="$(swift build --package-path .tools/interceptor/Packages/InterceptorAutomation --configuration release --show-bin-path)/interceptor-repository"
TASK_URL=$(python3 -c 'import json; print(json.load(open("repository-config.json"))["repositoryURL"])')
TASK_PREVIOUS=0
if python3 tools/fetch_previous.py --url "$TASK_URL" --output build/evidence/previous.json; then
    TASK_PREVIOUS=$("$TASK_VERIFIER" previous "$TASK_ROOT" "$TASK_ROOT/build/evidence/previous.json")
else
    TASK_FETCH_STATUS=$?
    [[ "$TASK_FETCH_STATUS" == 3 ]] || exit "$TASK_FETCH_STATUS"
fi
TASK_SEQUENCE=$(python3 - "$TASK_PREVIOUS" <<'PY'
import sys, time
previous = int(sys.argv[1]); sequence = time.time_ns() // 1_000_000
if not 1 <= sequence <= 9_007_199_254_740_991 or sequence <= previous:
    raise SystemExit('sequence did not increase; inspect clock or prior metadata')
print(sequence)
PY
)
TASK_REPO_ID=$(python3 -c 'import json; print(json.load(open("repository-config.json"))["id"])')
TASK_REPO_NAME=$(python3 -c 'import json; print(json.load(open("repository-config.json"))["name"])')
python3 tools/build.py --root "$TASK_ROOT" --output "$TASK_ROOT/build/site"
"$TASK_PUBLISHER" publish "$TASK_ROOT/build/site" --id "$TASK_REPO_ID" --name "$TASK_REPO_NAME" --sequence "$TASK_SEQUENCE" --key "$INTERCEPTOR_SIGNING_KEY_PATH"
"$TASK_VERIFIER" verify-local "$TASK_ROOT" "$TASK_ROOT/build/site" --signed
printf '%s\n' "$TASK_SEQUENCE" > build/sequence.txt
