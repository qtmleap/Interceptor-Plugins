import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class BootstrapTests(unittest.TestCase):
    def test_old_swift_fails_before_fetch_or_cache_creation(self):
        with tempfile.TemporaryDirectory(prefix="interceptor-old-swift-") as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            shutil.copy(Path(__file__).resolve().parents[1] / "bootstrap.sh", root / "tools" / "bootstrap.sh")
            (root / "repository-config.json").write_text(json.dumps({"upstreamRevision": "50307c2af38be2524f988e3d1d8a950973d63fd5"}))
            binary = root / "bin"
            binary.mkdir()
            (binary / "swift").write_text("#!/bin/sh\nprintf '%s\\n' 'Apple Swift version 6.1.2'\n")
            (binary / "git").write_text("#!/bin/sh\nexit 97\n")
            for p in binary.iterdir():
                p.chmod(0o755)
            result = subprocess.run(["bash", str(root / "tools" / "bootstrap.sh")], env=dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"]), capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Swift 6.4", result.stderr)
            self.assertFalse((root / ".tools").exists())


    def fixture(self, root, *, fresh=False, ignored=False):
        """Reuse an existing commit in real local Git repos; never create commits."""
        original = Path(__file__).resolve().parents[2]
        (root / 'tools').mkdir()
        shutil.copy(original / 'tools/bootstrap.sh', root / 'tools/bootstrap.sh')
        git = shutil.which('git')
        pin = subprocess.check_output([git, '-C', str(original), 'rev-parse', 'HEAD'], text=True).strip()
        (root / 'repository-config.json').write_text(json.dumps({'upstreamRevision': pin}))
        binary = root / 'bin'
        binary.mkdir()
        (binary / 'swift').write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo "Apple Swift version 6.4"; else touch "$PUBLISHER_EXECUTED"; fi\n')
        (binary / 'xcodebuild').write_text('#!/bin/sh\necho "Xcode 27.0"\n')
        cache = root / '.tools/interceptor'
        extra = 'Packages/InterceptorAutomation/Sources/RepositoryPublisher/Unexpected.swift'
        if fresh:
            # Real Git handles init/fetch/sparse checkout/status. Only fetch's
            # transport is redirected to an existing local repository; inject
            # the harmless file after checkout to exercise the common gate.
            dispatcher = f"""#!{sys.executable}
import os, pathlib, subprocess, sys
args = sys.argv[1:]
if 'fetch' in args:
    args[args.index('origin')] = {str(original)!r}
result = subprocess.run([{git!r}, *args])
if result.returncode == 0 and 'checkout' in args:
    root = pathlib.Path(args[args.index('-C') + 1])
    path = root / {extra!r}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('// harmless extra source\\n')
    if {ignored!r}:
        with (root / '.git/info/exclude').open('a') as handle:
            handle.write('/' + {extra!r} + '\\n')
sys.exit(result.returncode)
"""
            (binary / 'git').write_text(dispatcher)
        else:
            cache.parent.mkdir()
            subprocess.run([git, 'clone', '--quiet', '--no-hardlinks', '--no-checkout', str(original), str(cache)], check=True)
            subprocess.run([git, '-C', str(cache), 'remote', 'set-url', 'origin', 'https://github.com/qtmleap/Interceptor.git'], check=True)
            subprocess.run([git, '-C', str(cache), 'sparse-checkout', 'set', 'Packages/InterceptorAutomation'], check=True)
            subprocess.run([git, '-C', str(cache), '-c', 'advice.detachedHead=false', 'checkout', '--quiet', '--detach', pin], check=True)
        for path in binary.iterdir():
            path.chmod(0o755)
        marker = root / 'publisher-executed'
        environment = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'], PUBLISHER_EXECUTED=str(marker))
        return cache, cache / extra, marker, environment

    def test_untracked_and_ignored_extra_sources_are_rejected_before_build(self):
        for fresh in (False, True):
            for ignored in (False, True):
                with self.subTest(fresh=fresh, ignored=ignored), tempfile.TemporaryDirectory(prefix='interceptor-extra-source-') as directory:
                    root = Path(directory)
                    cache, extra, marker, environment = self.fixture(root, fresh=fresh, ignored=ignored)
                    if not fresh:
                        extra.parent.mkdir(parents=True, exist_ok=True)
                        extra.write_text('// harmless extra source\n')
                        if ignored:
                            with (cache / '.git/info/exclude').open('a') as handle:
                                handle.write('/' + str(extra.relative_to(cache)) + '\n')
                    result = subprocess.run(['bash', '-c', 'tools/bootstrap.sh && swift build'], cwd=root,
                                            env=environment, capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('unexpected', result.stderr.lower())
                    self.assertFalse(marker.exists(), 'the publisher build must not execute')
                    self.assertTrue(extra.exists(), 'preserve unexpected source for inspection')

    def test_clean_sparse_cache_allows_only_its_real_swiftpm_build_directory(self):
        with tempfile.TemporaryDirectory(prefix='interceptor-build-cache-') as directory:
            root = Path(directory)
            cache, extra, marker, environment = self.fixture(root)
            build = cache / 'Packages/InterceptorAutomation/.build'
            build.mkdir(parents=True)
            (build / 'build.db').write_text('fixture SwiftPM output')
            result = subprocess.run(['bash', str(root / 'tools/bootstrap.sh')], cwd=root,
                                    env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(marker.exists())
            nested = cache / 'Packages/InterceptorAutomation/Sources/RepositoryPublisher/.build/Unexpected.swift'
            nested.parent.mkdir(parents=True)
            nested.write_text('// a nested ignored directory is still an extra input\n')
            result = subprocess.run(['bash', str(root / 'tools/bootstrap.sh')], cwd=root,
                                    env=environment, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('unexpected', result.stderr.lower())
            self.assertTrue(nested.exists())


    def test_out_of_cone_non_source_inputs_and_symlinked_build_cache_are_rejected(self):
        for kind in ('out-of-cone', 'symlinked-build'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='interceptor-cache-boundary-') as directory:
                root = Path(directory)
                cache, _, marker, environment = self.fixture(root)
                if kind == 'out-of-cone':
                    unexpected = cache / 'OtherPackage/extra-input.json'
                    unexpected.parent.mkdir()
                    unexpected.write_text('{}')
                    with (cache / '.git/info/exclude').open('a') as handle:
                        handle.write('/OtherPackage/\n')
                else:
                    external = root / 'external-build'
                    external.mkdir()
                    (external / 'build.db').write_text('outside the owned cache')
                    unexpected = cache / 'Packages/InterceptorAutomation/.build'
                    unexpected.parent.mkdir(parents=True)
                    unexpected.symlink_to(external, target_is_directory=True)
                result = subprocess.run(['bash', str(root / 'tools/bootstrap.sh')], cwd=root,
                                        env=environment, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('unexpected', result.stderr.lower())
                self.assertFalse(marker.exists())
                self.assertTrue(unexpected.exists())


if __name__ == "__main__":
    unittest.main()
