"""build:dev wraps the canonical build with an owned, lock-protected, success-only output replacement."""
import fcntl
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from helpers import Case, REPO, tree_digest
import test_filesystem_hooks as filesystem_hooks


class BuildDevTests(Case):
    def routed_root(self):
        helper = filesystem_hooks.FilesystemHooksTests()
        helper.tmp = self.tmp
        root = helper.routed_root()
        shutil.copy(REPO / "tools/build_dev.py", root / "tools")
        return root

    def dev(self, root):
        return self.run_tool(root, "build_dev")

    def package(self, root):
        return root / "build/dev/plugins/demo.json"

    def break_source(self, root):
        (root / "plugins/demo/hooks/api.example.com/search/POST.ts").write_text("const broken: = ;\n")

    def test_real_schema2_build_twice_is_deterministic_and_owned(self):
        root = self.routed_root()
        self.ok(self.dev(root))
        first = self.package(root).read_bytes()
        package = json.loads(first)
        self.assertEqual(set(package), {"manifest", "sourceFiles"})
        self.assertTrue((root / "build/dev/.build-dev-owned").is_file())
        digest = tree_digest(root / "build/dev")
        self.ok(self.dev(root))
        self.assertEqual(self.package(root).read_bytes(), first)
        self.assertEqual(tree_digest(root / "build/dev"), digest)
        self.assertEqual([p.name for p in (root / "build").iterdir() if p.name.startswith(".dev.")], [".dev.lock"])

    def test_stale_package_is_removed_on_success(self):
        root = self.routed_root()
        self.ok(self.dev(root))
        (root / "build/dev/plugins/stale.json").write_text("{}")
        self.ok(self.dev(root))
        self.assertEqual([p.name for p in (root / "build/dev/plugins").iterdir()], ["demo.json"])

    def test_compiler_failure_preserves_previous_output_and_sources(self):
        root = self.routed_root()
        self.ok(self.dev(root))
        before = tree_digest(root / "build/dev")
        self.break_source(root)
        sources = tree_digest(root / "plugins")
        (root / "build/scripts").mkdir(exist_ok=True)
        (root / "build/scripts/sentinel").write_text("keep")
        self.fails(self.dev(root))
        self.assertEqual(tree_digest(root / "build/dev"), before)
        self.assertEqual(tree_digest(root / "plugins"), sources)
        self.assertEqual((root / "build/scripts/sentinel").read_text(), "keep")
        self.assertFalse([p for p in (root / "build").iterdir() if ".stage." in p.name])

    def test_unowned_output_is_refused_untouched(self):
        root = self.routed_root()
        (root / "build/dev").mkdir(parents=True)
        (root / "build/dev/mine.txt").write_text("user")
        before = tree_digest(root / "build/dev")
        self.fails(self.dev(root))
        self.assertEqual(tree_digest(root / "build/dev"), before)

    def test_symlinked_output_build_and_root_are_refused(self):
        root = self.routed_root()
        target = self.tmp / "elsewhere"
        target.mkdir()
        (root / "build").mkdir()
        (root / "build/dev").symlink_to(target, target_is_directory=True)
        self.fails(self.dev(root))
        self.assertEqual(list(target.iterdir()), [])
        (root / "build/dev").unlink()
        shutil.rmtree(root / "build")
        (root / "build").symlink_to(target, target_is_directory=True)
        self.fails(self.dev(root))
        self.assertEqual(list(target.iterdir()), [])
        (root / "build").unlink()
        link = self.tmp / "root-link"
        link.symlink_to(root, target_is_directory=True)
        self.fails(subprocess.run([sys.executable, str(root / "tools/build_dev.py"), "--root", str(link)],
                                  capture_output=True, text=True))

    def test_symlinked_root_ancestor_is_refused(self):
        root = self.routed_root()
        link = self.tmp / 'ancestor-link'
        link.symlink_to(root.parent, target_is_directory=True)
        result = self.dev(link / root.name)
        self.fails(result)
        self.assertIn(f'symlinked root path: {link}', result.stderr)
        self.assertFalse((root / 'build/dev').exists())

    def test_promotion_failure_restores_previous_output(self):
        sys.path.insert(0, str(REPO / 'tools'))
        self.addCleanup(sys.path.remove, str(REPO / 'tools'))
        import build_dev
        root = self.routed_root()
        self.ok(self.dev(root))
        output = root / 'build/dev'
        before = tree_digest(output)
        stage = root / 'build/.dev.stage.test'
        shutil.copytree(output, stage)
        (stage / 'plugins/demo.json').write_text('new package')
        rename = os.rename
        def fail_promotion(source, target):
            if source == stage:
                raise OSError('promotion failed')
            return rename(source, target)
        with patch.object(build_dev.os, 'rename', side_effect=fail_promotion):
            with self.assertRaises(OSError):
                build_dev.replace(root / 'build', stage, output)
        self.assertEqual(tree_digest(output), before)
        self.assertTrue(stage.is_dir())

    def test_backup_cleanup_failure_reports_published_output(self):
        sys.path.insert(0, str(REPO / 'tools'))
        self.addCleanup(sys.path.remove, str(REPO / 'tools'))
        import build_dev
        root = self.routed_root()
        self.ok(self.dev(root))
        output = root / 'build/dev'
        stage = root / 'build/.dev.stage.test'
        shutil.copytree(output, stage)
        (stage / 'plugins/demo.json').write_text('new package')
        with patch.object(build_dev, 'remove_owned', side_effect=PermissionError('cleanup denied')):
            with self.assertRaisesRegex(build_dev.ToolError, 'new packages published'):
                build_dev.replace(root / 'build', stage, output)
        self.assertEqual((output / 'plugins/demo.json').read_text(), 'new package')
        self.assertEqual(len(list((root / 'build').glob('.dev.backup.*'))), 1)

    def test_marker_symlink_is_not_ownership(self):
        root = self.routed_root()
        self.ok(self.dev(root))
        marker = root / 'build/dev/.build-dev-owned'
        actual = root / 'marker'
        marker.rename(actual)
        marker.symlink_to(actual)
        before = tree_digest(root / 'build/dev')
        self.fails(self.dev(root))
        self.assertEqual(tree_digest(root / 'build/dev'), before)

    def test_existing_site_output_is_not_touched(self):
        root = self.routed_root()
        (root / "build/site").mkdir(parents=True)
        (root / "build/site/keep").write_text("site")
        self.ok(self.dev(root))
        self.assertEqual((root / "build/site/keep").read_text(), "site")

    def test_generated_schema2_package_runs_in_real_simulator(self):
        binary = Path(os.environ.get('INTERCEPTOR_SIMULATOR', REPO / '.tools/bin/interceptor-simulator'))
        self.assertTrue(binary.is_file(), 'build the Rust simulator with tools/build-runtime.sh')
        root = self.routed_root()
        self.ok(self.dev(root))
        event = self.tmp / 'event.json'
        event.write_text(json.dumps({'phase': 'request.onEnter', 'request': {
            'method': 'POST', 'host': 'api.example.com', 'path': '/search', 'body': {'limit': 50}}}))
        config = self.tmp / 'config.json'
        config.write_text('{"endpoints": {}}')
        result = subprocess.run([str(binary), 'run-package', str(self.package(root)), 'request.onEnter',
                                 str(event), str(config)], capture_output=True, text=True, timeout=10)
        self.ok(result)
        self.assertEqual(json.loads(result.stdout), {'actions': [], 'mutation': {'body': {'limit': 5}}})

    def test_unowned_output_does_not_discard_recovery_backup(self):
        root = self.routed_root()
        self.ok(self.dev(root))
        backup = root / 'build/.dev.backup.crash'
        (root / 'build/dev').rename(backup)
        (root / 'build/dev').mkdir()
        (root / 'build/dev/user.txt').write_text('keep')
        before = tree_digest(root / 'build')
        self.fails(self.dev(root))
        self.assertEqual(tree_digest(root / 'build'), before)

    def test_concurrent_invocation_is_rejected_and_output_unchanged(self):
        root = self.routed_root()
        (root / "build").mkdir()
        fd = os.open(root / "build/.dev.lock", os.O_RDWR | os.O_CREAT)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        result = self.dev(root)
        self.fails(result)
        self.assertIn("another build:dev", result.stderr)
        self.assertFalse((root / "build/dev").exists())

    def test_interrupted_replacement_is_recovered(self):
        root = self.routed_root()
        self.ok(self.dev(root))
        os.rename(root / "build/dev", root / "build/.dev.backup.crash")
        self.break_source(root)
        self.fails(self.dev(root))
        self.assertTrue(self.package(root).is_file())
        self.assertFalse((root / "build/.dev.backup.crash").exists())
