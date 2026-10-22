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
        for folder in ('plugins', 'src', 'scripts', 'manifests'):
            if (root / folder).exists():
                shutil.copytree(root / folder, configured / folder)
        native_site = temp / 'native'
        run(sys.executable, root / 'tools/build.py', '--root', root, '--output', native_site)
        portable_site = temp / 'portable'; shutil.copytree(native_site, portable_site)
        for tool, site in ((args.publisher, native_site), (portable, portable_site)):
            run(tool, 'publish', site, '--id', config['id'], '--name', config['name'], '--sequence', '42', '--key', key)
            for verifier in (args.verifier, portable):
                run(verifier, 'verify-local', configured, site, '--signed')
        # Both source verifiers compare exact UTF-8, not Swift's canonical String equality.
        shutil.copytree(root / 'fixtures', configured / 'fixtures')
        shutil.copytree(root / 'build/scripts', configured / 'build/scripts')
        mismatch = temp / 'source-mismatch'; shutil.copytree(portable_site, mismatch)
        package_path = mismatch / 'plugins/request-summary.json'
        package = json.loads(package_path.read_text())
        selected = package['manifest']['matches'][0]['hooks']['request']['onEnter']
        original = package['sourceFiles'][selected]
        package['sourceFiles'][selected] = original + "\nconst marker = 'caf\u00e9';\n"
        package_path.write_text(json.dumps(package, ensure_ascii=False))
        (configured / 'build/scripts/request-summary' / selected).write_text(original + "\nconst marker = 'cafe\u0301';\n")
        for verifier in (args.verifier, portable):
            result = subprocess.run([str(verifier), 'samples', str(configured), str(mismatch)], capture_output=True)
            assert result.returncode != 0 and b'sourceFiles differ' in result.stderr, result.stderr.decode(errors='replace')
        print('Swift/Python source verification rejects Unicode-equivalent but byte-distinct JavaScript.')
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
