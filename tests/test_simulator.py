"""The standalone Rust simulator must parse without executing, and run the real bridge."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get('INTERCEPTOR_SIMULATOR', ROOT / '.tools/bin/interceptor-simulator'))


class SimulatorTests(unittest.TestCase):
    def invoke(self, *args):
        self.assertTrue(BINARY.is_file(), 'build the Rust simulator with tools/build-runtime.sh')
        return subprocess.run([str(BINARY), *map(str, args)], capture_output=True, timeout=10)

    def test_check_never_executes_and_run_times_out_as_negative_control(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'loop.js'; source.write_text('while (true) {}')
            event = Path(directory) / 'event.json'; event.write_text('{}')
            checked = self.invoke('check', source)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            run = self.invoke('run', source, 'onRequest', event, event)
            self.assertEqual(run.returncode, 1, run.stderr)

    def test_syntax_error_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'bad.js'; source.write_text('function onRequest( {')
            result = self.invoke('check', source)
            self.assertEqual(result.returncode, 6, result.stderr)
            self.assertTrue(result.stderr)

    def test_top_level_throw_is_only_reported_by_run(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'throw.js'; source.write_text('throw new Error("boom")')
            event = Path(directory) / 'event.json'; event.write_text('{}')
            self.assertEqual(self.invoke('check', source).returncode, 0)
            self.assertEqual(self.invoke('run', source, 'onRequest', event, event).returncode, 6)

    def test_rejects_invalid_inputs_without_running_them(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.js'
            for value in (b'', b'\xff', b'const x=1;\x00', b' ' * 131073):
                with self.subTest(value=value[:12]):
                    source.write_bytes(value)
                    self.assertEqual(self.invoke('check', source).returncode, 4)
            source.write_text('function onRequest() { return {actions: []}; }')
            alias = Path(directory) / 'alias.js'; alias.symlink_to(source)
            self.assertEqual(self.invoke('check', alias).returncode, 4)

    def test_run_checks_result_and_runtime_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.js'
            event = Path(directory) / 'event.json'; event.write_text('{}')
            for code, expected in (('function onRequest() { return {bad: true}; }', 5),
                                   ('const noHook = 1;', 6),
                                   ('function onRequest() { return {actions: []}; }', 0)):
                source.write_text(code)
                result = self.invoke('run', source, 'onRequest', event, event)
                self.assertEqual(result.returncode, expected, result.stderr)
                if expected == 0:
                    self.assertEqual(result.stdout.strip(), b'{"actions":[]}')

    def test_compile_only_entry_has_no_execution_call(self):
        import re
        text = (ROOT / 'tools/simulator/csrc/check.c').read_text()
        text = re.sub(r'//[^\n]*|/\*.*?\*/', '', text, flags=re.S)
        for forbidden in ('JS_EvalFunction', 'JS_Call', 'JS_ExecutePendingJob', 'qjs_run'):
            self.assertNotRegex(text, rf'\b{forbidden}\s*\(')
        self.assertIn('JS_EVAL_FLAG_COMPILE_ONLY', text)

    def test_run_requires_core_compatible_json_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.js'; source.write_text('function onRequest() { return {actions: []}; }')
            event = Path(directory) / 'event.json'
            config = Path(directory) / 'config.json'; config.write_text('{}')
            for text in ('[]', '1', '"text"', 'null', '{"n":9007199254740992}', '{"x":1,"x":2}'):
                with self.subTest(text=text):
                    event.write_text(text)
                    self.assertEqual(self.invoke('run', source, 'onRequest', event, config).returncode, 4)
                    self.assertEqual(self.invoke('run', source, 'onRequest', config, event).returncode, 4)

    def test_engine_flags_and_limits_match_the_pinned_app(self):
        import math
        import re
        package = Path(os.environ.get('INTERCEPTOR_AUTOMATION_PACKAGE',
                                      BINARY.parent.parent / 'interceptor/Packages/InterceptorAutomation'))
        app = (package / 'Sources/AutomationRuntime/JavaScriptExecutor.swift').read_text()
        rust = (ROOT / 'tools/simulator/src/main.rs').read_text()
        def product(text):
            return math.prod(int(part.strip().replace('_', '')) for part in text.split('*'))
        native = {key: product(value) for key, value in re.findall(r'public static let (\w+) = ([0-9_ *]+)', app)}
        actual = {key: product(value) for key, value in re.findall(r'\b(\w+):\s*([0-9_]+(?:\s*\*\s*[0-9_]+)*)\s*[,}]', rust)}
        fields = {'deadlineMilliseconds':'deadline_ms','heapBytes':'heap_bytes','stackBytes':'stack_bytes',
                  'maxSourceBytes':'max_source_bytes','maxEventBytes':'max_event_bytes','maxConfigBytes':'max_config_bytes',
                  'maxResultBytes':'max_result_bytes','maxResultDepth':'max_result_depth','maxActions':'max_actions'}
        for native_key, rust_key in fields.items():
            self.assertEqual(native[native_key], actual[rust_key], native_key)
        manifest = (package / 'Package.swift').read_text()
        build = (ROOT / 'tools/simulator/build.rs').read_text()
        for flag in ('-fwrapv', '-funsigned-char'):
            self.assertIn(flag, manifest)
            self.assertIn(flag, build)
        self.assertIn('cLanguageStandard: .gnu11', manifest)
        self.assertIn('-std=gnu11', build)
