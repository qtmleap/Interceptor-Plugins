#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$TASK_ROOT"
tools/check-authoring.sh
export INTERCEPTOR_SIMULATOR="$TASK_ROOT/.tools/bin/interceptor-simulator"
tools/bootstrap-native.sh
TASK_TEMP=$(mktemp -d /tmp/interceptor-sample-check.XXXXXX)
trap 'rm -rf -- "$TASK_TEMP"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python3 tools/build.py --root "$TASK_ROOT" --output "$TASK_TEMP/site"
cp -R "$TASK_TEMP/site" "$TASK_TEMP/repro"
swift build --package-path .tools/interceptor/Packages/InterceptorAutomation --configuration release --product interceptor-repository > build/evidence/publisher-build.log 2>&1 || { tail -60 build/evidence/publisher-build.log; exit 1; }
swift build --package-path tools/Verifier --configuration release > build/evidence/verifier-build.log 2>&1 || { tail -60 build/evidence/verifier-build.log; exit 1; }
TASK_PUBLISHER="$(swift build --package-path .tools/interceptor/Packages/InterceptorAutomation --configuration release --show-bin-path)/interceptor-repository"
TASK_VERIFIER="$(swift build --package-path tools/Verifier --configuration release --show-bin-path)/interceptor-samples-check"
TASK_REPO_ID=$(python3 -c 'import json; print(json.load(open("repository-config.json"))["id"])')
TASK_REPO_NAME=$(python3 -c 'import json; print(json.load(open("repository-config.json"))["name"])')
TASK_REPOSITORY=$(python3 -c 'import json; print(json.load(open("repository-config.json"))["githubRepository"])')
if python3 -c 'import json,sys; sys.exit(json.load(open("repository-config.json"))["publicKeyFingerprint"] is None)'; then
    python3 tools/guard.py --root "$TASK_ROOT" --repository "$TASK_REPOSITORY" --ref refs/heads/master
fi
"$TASK_VERIFIER" samples "$TASK_ROOT" "$TASK_TEMP/site"
python3 tools/tests/check_template.py --root "$TASK_ROOT" --verifier "$TASK_VERIFIER" --publisher "$TASK_PUBLISHER"
"$TASK_PUBLISHER" publish "$TASK_TEMP/site" --id "$TASK_REPO_ID" --name "$TASK_REPO_NAME" --sequence 1
"$TASK_VERIFIER" verify-local "$TASK_ROOT" "$TASK_TEMP/site"

# A known wrong event shape must fail the expected-output checks, not silently yield undefined text.
cp -R "$TASK_TEMP/repro" "$TASK_TEMP/wrong-shape"
mkdir -p "$TASK_TEMP/wrong-root"
cp -R manifests fixtures "$TASK_TEMP/wrong-root/"
cp -R build/scripts "$TASK_TEMP/wrong-root/scripts"
cp repository-config.json "$TASK_TEMP/wrong-root/"
python3 - "$TASK_TEMP/wrong-shape/plugins/request-summary.json" "$TASK_TEMP/wrong-root/scripts/request-summary.js" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); package = json.loads(p.read_text())
package['source'] = "function onRequest(event, config) { return {actions:[{type:'webhook',endpointId:config.endpoints.preview,json:{summary:event.method+' '+event.host+event.path}}]}; }"
p.write_text(json.dumps(package))
Path(sys.argv[2]).write_text(package['source'])
PY
if "$TASK_VERIFIER" samples "$TASK_TEMP/wrong-root" "$TASK_TEMP/wrong-shape" > build/evidence/wrong-shape.log 2>&1; then
    echo 'wrong event shape unexpectedly passed' >&2; exit 1
fi
grep -q 'sample cases failed' build/evidence/wrong-shape.log

# Tests use a temporary config and key, never the official secret or committed fingerprint.
mkdir -p "$TASK_TEMP/root"
cp -R manifests "$TASK_TEMP/root/"
TASK_TEST_FP=$("$TASK_PUBLISHER" keygen "$TASK_TEMP/test.key")
python3 - "$TASK_TEMP/root/repository-config.json" "$TASK_TEST_FP" <<'PY'
import json, sys
from pathlib import Path
config = json.load(open('repository-config.json'))
config['publicKeyFingerprint'] = sys.argv[2]
Path(sys.argv[1]).write_text(json.dumps(config))
PY
"$TASK_PUBLISHER" publish "$TASK_TEMP/repro" --id "$TASK_REPO_ID" --name "$TASK_REPO_NAME" --sequence 2 --key "$TASK_TEMP/test.key"
"$TASK_VERIFIER" verify-local "$TASK_TEMP/root" "$TASK_TEMP/repro" --signed
cp "$TASK_TEMP/repro/repository.json" "$TASK_TEMP/current-envelope.saved"
swift tools/tests/HistoryFixture.swift "$TASK_TEMP/current-envelope.saved" "$TASK_TEMP/test.key" "$TASK_TEMP/repro/repository.json" expired
[[ "$("$TASK_VERIFIER" previous "$TASK_TEMP/root" "$TASK_TEMP/repro/repository.json")" == 2 ]]
if "$TASK_VERIFIER" verify-local "$TASK_TEMP/root" "$TASK_TEMP/repro" --signed > build/evidence/expired-import.log 2>&1; then
    echo 'expired metadata unexpectedly accepted for import' >&2; exit 1
fi
swift tools/tests/HistoryFixture.swift "$TASK_TEMP/current-envelope.saved" "$TASK_TEMP/test.key" "$TASK_TEMP/repro/repository.json" future
if "$TASK_VERIFIER" previous "$TASK_TEMP/root" "$TASK_TEMP/repro/repository.json" > build/evidence/future-history.log 2>&1; then
    echo 'future-issued metadata unexpectedly accepted for renewal' >&2; exit 1
fi
cp "$TASK_TEMP/current-envelope.saved" "$TASK_TEMP/repro/repository.json"
cp "$TASK_TEMP/repro/plugins/request-summary.json" "$TASK_TEMP/package.saved"
python3 - "$TASK_TEMP/repro/plugins/request-summary.json" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1]); data = bytearray(p.read_bytes()); data[len(data)//2] ^= 1; p.write_bytes(data)
PY
if "$TASK_VERIFIER" verify-local "$TASK_TEMP/root" "$TASK_TEMP/repro" --signed > build/evidence/tampered-package.log 2>&1; then
    echo 'tampered package unexpectedly accepted' >&2; exit 1
fi
cp "$TASK_TEMP/package.saved" "$TASK_TEMP/repro/plugins/request-summary.json"
cp "$TASK_TEMP/repro/repository.json" "$TASK_TEMP/envelope.saved"
python3 - "$TASK_TEMP/repro/repository.json" <<'PY'
import base64, json, sys
from pathlib import Path
p = Path(sys.argv[1]); envelope = json.loads(p.read_text())
data = bytearray(base64.b64decode(envelope['payload'])); data[len(data)//2] ^= 1
envelope['payload'] = base64.b64encode(data).decode(); p.write_text(json.dumps(envelope))
PY
if "$TASK_VERIFIER" verify-local "$TASK_TEMP/root" "$TASK_TEMP/repro" --signed > build/evidence/tampered-envelope.log 2>&1; then
    echo 'tampered signed payload unexpectedly accepted' >&2; exit 1
fi
cp "$TASK_TEMP/envelope.saved" "$TASK_TEMP/repro/repository.json"
python3 - "$TASK_TEMP/root/repository-config.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); config = json.loads(p.read_text()); config['publicKeyFingerprint'] = '0'*64
p.write_text(json.dumps(config))
PY
if "$TASK_VERIFIER" verify-local "$TASK_TEMP/root" "$TASK_TEMP/repro" --signed > build/evidence/wrong-fingerprint.log 2>&1; then
    echo 'wrong signing key unexpectedly accepted' >&2; exit 1
fi
if "$TASK_VERIFIER" previous "$TASK_TEMP/root" "$TASK_TEMP/repro/repository.json" > build/evidence/wrong-history-key.log 2>&1; then
    echo 'previous accepted an unexpected signing key' >&2; exit 1
fi
python3 - "$TASK_TEMP/root/repository-config.json" "$TASK_TEST_FP" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); config = json.loads(p.read_text())
config['publicKeyFingerprint'] = sys.argv[2]; config['id'] = '11111111-2222-4333-8444-555555555555'
p.write_text(json.dumps(config))
PY
if "$TASK_VERIFIER" previous "$TASK_TEMP/root" "$TASK_TEMP/repro/repository.json" > build/evidence/wrong-history-id.log 2>&1; then
    echo 'previous accepted an unexpected repository UUID' >&2; exit 1
fi
echo 'All sample, generation, HTTPS and integrity checks passed.'
python3 tools/tests/check_signing_compatibility.py --root "$TASK_ROOT" --publisher "$TASK_PUBLISHER" --verifier "$TASK_VERIFIER"
