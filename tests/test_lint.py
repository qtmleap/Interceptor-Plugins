"""Run the configured Biome rules against isolated authored-source probes."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class LintTests(unittest.TestCase):
    def lint(self, source, relative_path='plugins/demo/hooks/example.com/POST.ts'):
        with tempfile.TemporaryDirectory(prefix='interceptor-lint-') as directory:
            root = Path(directory).resolve()
            config = json.loads((ROOT / 'biome.json').read_text())
            config['plugins'] = [str((ROOT / path).resolve()) for path in config['plugins']]
            (root / 'biome.json').write_text(json.dumps(config))
            probe = root / relative_path
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text(source)
            control = root / 'plugins/lint-control.ts'
            control.parent.mkdir(parents=True, exist_ok=True)
            control.write_text('const control = 1;\n')
            return subprocess.run(['bun', str(ROOT / 'node_modules/@biomejs/biome/bin/biome'),
                                   'lint', '--error-on-warnings', '.'], cwd=root,
                                  capture_output=True, text=True)

    def test_const_and_let_in_text_or_property_names_are_allowed(self):
        result = self.lint('const text = "let x = 1"; const object = {let: 1}; // let ignored\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_mutable_declarations_are_rejected_including_loop_bindings(self):
        for source in ['let value = 1;', 'let value;', 'let value: number;',
                       'let {value} = {value: 1};', 'let [value] = [1];',
                       'for (let i = 0; i < 1; i++) {}',
                       'for (let value of [1]) {}', 'for (let key in {}) {}',
                       'let\nvalue = 1;', 'let /* reason */ value = 1;',
                       '// why\nlet value = 1;', '/** reason */\nlet value = 1;',
                       '\n   let value = 1;', 'declare let value: number;',
                       'export let value = 1;',
                       'Interceptor.attach({response: {async onLeave() { let value = 1; }}});',
                       'const helper = () => { let value; };']:
            with self.subTest(source=source):
                result = self.lint(source)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('Mutable bindings are forbidden', result.stdout + result.stderr)

    def test_var_is_rejected(self):
        result = self.lint('var value = 1;')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('lint/suspicious/noVar', result.stdout + result.stderr)

    def test_authored_javascript_and_fixture_hooks_are_checked(self):
        for path in ['tools/probe.js', 'fixtures/legacy-v1/src/probe.js',
                     'fixtures/outbound-example/hooks/example.com/GET.ts', 'probe.js']:
            with self.subTest(path=path):
                result = self.lint('let value = 1;', path)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Mutable bindings are forbidden', result.stdout + result.stderr)

    def test_dependency_and_generated_sources_are_excluded(self):
        for path in ['node_modules/vendor/probe.js', 'biome-plugins/probe.js',
                     'build/scripts/probe.js', '.tools/cache/probe.js', '.codex/probe.js']:
            with self.subTest(path=path):
                result = self.lint('let value = 1;', path)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
