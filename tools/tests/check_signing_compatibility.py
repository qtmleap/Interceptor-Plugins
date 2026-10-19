#!/usr/bin/env python3
"""Two-way independent compatibility check: Bun Ed25519 publisher vs app Swift libraries."""
import argparse
import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--publisher', required=True)
    parser.add_argument('--verifier', required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    portable = root / 'tools/repository-tool'

    def run(*argv, expected=0):
        result = subprocess.run([str(x) for x in argv], capture_output=True, cwd=root)
        if result.returncode != expected:
            raise RuntimeError(f'compatibility command failed: {Path(str(argv[0])).name} {argv[1]}: {result.stderr.decode(errors="replace")}')
        return result.stdout.decode().strip()

    with tempfile.TemporaryDirectory(prefix='interceptor-compatibility-') as directory:
        temp = Path(directory)
        key = temp / 'test.key'
        key.write_bytes(bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60'))
        key.chmod(0o600)
        fingerprint = run(portable, 'fingerprint', key)
        config = json.loads((root / 'repository-config.json').read_text())
        config['publicKeyFingerprint'] = fingerprint
        configured = temp / 'configured'; configured.mkdir()
        (configured / 'repository-config.json').write_text(json.dumps(config))
        shutil.copytree(root / 'manifests', configured / 'manifests')
        native_site = temp / 'native'
        run(sys.executable, root / 'tools/build.py', '--root', root, '--output', native_site)
        portable_site = temp / 'portable'; shutil.copytree(native_site, portable_site)
        for tool, site in ((args.publisher, native_site), (portable, portable_site)):
            run(tool, 'publish', site, '--id', config['id'], '--name', config['name'], '--sequence', '42', '--key', key)
            for verifier in (args.verifier, portable):
                run(verifier, 'verify-local', configured, site, '--signed')
        # Each implementation signs history that the other must verify.
        for generator, source, verifier in ((root / 'tools/tests/history_fixture.py', portable_site, args.verifier),
                                            (root / 'tools/tests/HistoryFixture.swift', native_site, portable)):
            command = sys.executable if str(generator).endswith('.py') else 'swift'
            expired = temp / 'expired.json'; future = temp / 'future.json'
            run(command, generator, source / 'repository.json', key, expired, 'expired')
            assert run(verifier, 'previous', configured, expired) == '42'
            run(command, generator, source / 'repository.json', key, future, 'future')
            result = subprocess.run([str(verifier), 'previous', str(configured), str(future)], capture_output=True)
            assert result.returncode != 0, 'future history was accepted'
        print('Two-way Swift/Bun signature and authenticated-history compatibility passed.')


if __name__ == '__main__':
    main()
