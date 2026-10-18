"""Exercise the locked Bun authoring path independently of a Node installation."""
import json
import os
import shutil
import subprocess

from helpers import Case, REPO


class BunToolchainTests(Case):
    def test_clean_checkout_install_is_frozen_and_rejects_dependency_drift(self):
        root = self.tmp / 'fresh-install'
        root.mkdir()
        for name in ('package.json', 'bun.lock', '.bun-version'):
            shutil.copy(REPO / name, root / name)
        install_env = dict(os.environ, TMPDIR=str(self.tmp))
        install_env.setdefault('BUN_INSTALL_CACHE_DIR', str(self.tmp / 'bun-cache'))
        result = subprocess.run(['bun', 'install', '--frozen-lockfile', '--ignore-scripts'],
                                cwd=root, env=install_env, capture_output=True, text=True, timeout=120)
        self.ok(result)
        self.assertFalse((root / 'node_modules').is_symlink())
        self.assertEqual(json.loads((root / 'node_modules/typescript/package.json').read_text())['version'], '5.8.3')
        before = (root / 'bun.lock').read_bytes()
        package = json.loads((root / 'package.json').read_text())
        package['devDependencies']['typescript'] = '5.8.2'
        (root / 'package.json').write_text(json.dumps(package))
        result = subprocess.run(['bun', 'install', '--frozen-lockfile', '--ignore-scripts'],
                                cwd=root, env=install_env, capture_output=True, text=True, timeout=120)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('lockfile', result.stderr.lower())
        self.assertEqual((root / 'bun.lock').read_bytes(), before)

    def test_portable_checks_refuse_an_unpinned_runtime_before_other_tools(self):
        root = self.tmp / 'runtime-preflight'
        root.mkdir()
        (root / 'tools').mkdir()
        shutil.copy(REPO / 'tools/check-authoring.sh', root / 'tools/check-authoring.sh')
        shutil.copy(REPO / '.bun-version', root / '.bun-version')
        binary = root / 'bin'
        binary.mkdir()
        (binary / 'bun').write_text('#!/bin/sh\nprintf "0.0.0\\n"\n')
        (binary / 'bun').chmod(0o755)
        result = subprocess.run(['bash', str(root / 'tools/check-authoring.sh')],
                                env=dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH']),
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Bun', result.stderr)
        self.assertFalse((root / 'build').exists())
