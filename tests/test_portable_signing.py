"""A Linux user can create and reuse the app's raw Ed25519 key without Swift."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PortableSigningSmokeTests(unittest.TestCase):
    def command(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'tools/repository_tool.py'), *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True, timeout=30)

    def test_keygen_and_fingerprint_need_no_swift_and_do_not_clobber(self):
        with tempfile.TemporaryDirectory(prefix='interceptor-portable-key-') as directory:
            key = Path(directory) / 'repository.key'
            created = self.command('keygen', key)
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertRegex(created.stdout.strip(), r'^[0-9a-f]{64}$')
            self.assertEqual(len(key.read_bytes()), 32)
            self.assertEqual(key.stat().st_mode & 0o777, 0o600)
            original = key.read_bytes()
            reused = self.command('fingerprint', key)
            self.assertEqual(reused.returncode, 0, reused.stderr)
            self.assertEqual(reused.stdout, created.stdout)
            duplicate = self.command('keygen', key)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertEqual(key.read_bytes(), original)
            self.assertNotIn(original.hex(), created.stdout + created.stderr)

    def test_rfc8032_seed_keeps_the_same_public_fingerprint(self):
        with tempfile.TemporaryDirectory(prefix='interceptor-key-vector-') as directory:
            key = Path(directory) / 'test.key'
            key.write_bytes(bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60'))
            key.chmod(0o600)
            actual = self.command('fingerprint', key)
            expected = hashlib.sha256(bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')).hexdigest()
            self.assertEqual(actual.returncode, 0, actual.stderr)
            self.assertEqual(actual.stdout.strip(), expected)
