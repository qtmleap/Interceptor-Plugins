#!/usr/bin/env python3
"""Test-only expired/future metadata, authenticated by a disposable test key."""
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys


def main():
    source, key_path, output, mode = sys.argv[1:]
    if mode not in ('expired', 'future'):
        raise ValueError('invalid fixture mode')
    envelope = json.loads(Path(source).read_text())
    index = json.loads(base64.b64decode(envelope['payload'], validate=True))
    now = datetime.now(timezone.utc)
    issued = now - timedelta(days=31) if mode == 'expired' else now + timedelta(seconds=600)
    index['issuedAt'] = issued.strftime('%Y-%m-%dT%H:%M:%SZ')
    index['expiresAt'] = (issued + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    payload = json.dumps(index, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    key = Path(key_path).read_bytes()
    if len(key) != 32:
        raise ValueError('invalid test key')
    helper = Path(__file__).resolve().parents[1] / 'signing.mjs'
    signed = subprocess.run(['bun', str(helper), 'sign'], input=key + b'InterceptorRepository/v1\0' + payload,
                            capture_output=True, check=True)
    signature = bytes.fromhex(signed.stdout.decode().strip())
    envelope['payload'] = base64.b64encode(payload).decode()
    envelope['signature']['value'] = base64.b64encode(signature).decode()
    Path(output).write_text(json.dumps(envelope))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        sys.stderr.write('history fixture generation failed\n')
        raise SystemExit(1)
