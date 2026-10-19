"""Exercise the actual editor project with independent authored hook files."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EditorConfigTests(unittest.TestCase):
    def check_project(self, sources):
        with tempfile.TemporaryDirectory(prefix='hook-editor-') as temporary:
            root = Path(temporary)
            shutil.copy(ROOT / 'tsconfig.json', root)
            (root / 'types').mkdir()
            shutil.copy(ROOT / 'types/interceptor.d.ts', root / 'types')
            for name, source in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result = subprocess.run(['bun', str(ROOT / 'node_modules/typescript/bin/tsc'),
                                     '--project', str(root), '--pretty', 'false'],
                                    capture_output=True, text=True, timeout=30)
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(after, before, 'editor checking must never emit or alter files')
            return result

    def test_contextual_types_and_duplicate_helpers_in_independent_files(self):
        source = '''
const helper = (value: string) => value.length;
Interceptor.attach({request:{onEnter(req, cfg) {
  const method: string | undefined = req.method;
  const endpoint: string | undefined = cfg.endpoints.preview;
  req.body = {length: helper(method || endpoint || '')};
}}});
'''
        result = self.check_project({
            'plugins/demo/hooks/example.com/GET.ts': source,
            'plugins/demo/hooks/example.com/search/POST.ts': source,
            'src/legacy.ts': 'function onRequest(event: Interceptor.Event, config: Interceptor.Config): Interceptor.Result { return {actions: []}; }',
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_leave_and_response_request_writes_are_rejected(self):
        result = self.check_project({'plugins/demo/hooks/example.com/GET.ts': '''
Interceptor.attach({
  request:{onLeave(req) { req.body = {}; }},
  response:{onEnter(res) { res.request.body = {}; }, onLeave(res) { res.body = {}; }}
});
'''})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.count('TS2540'), 3, result.stdout + result.stderr)
        self.assertNotIn('TS7006', result.stdout, 'callbacks must receive contextual types')

    def test_unknown_fields_and_host_globals_are_rejected(self):
        result = self.check_project({'plugins/demo/hooks/example.com/GET.ts': '''
Interceptor.attach({request:{onEnter(req, cfg) {
  req.missing;
  cfg.missing;
  fetch('https://example.com');
  window.location;
  process.env;
  setTimeout(() => {}, 1);
}}});
'''})
        self.assertNotEqual(result.returncode, 0)
        for name in ('missing', 'fetch', 'window', 'process', 'setTimeout'):
            self.assertIn(name, result.stdout, result.stdout + result.stderr)
        self.assertNotIn('TS7006', result.stdout)

    def test_strict_index_and_optional_properties_match_authoring(self):
        result = self.check_project({'plugins/demo/hooks/example.com/GET.ts': '''
Interceptor.attach({request:{onEnter(req, cfg) {
  const endpoint: string = cfg.endpoints.preview;
  const config: Interceptor.Config = {endpoints: {}, settings: undefined};
}}});
'''})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('TS2322', result.stdout, result.stdout + result.stderr)
        self.assertIn('TS2375', result.stdout, result.stdout + result.stderr)

    def test_tasks_are_explicit_process_commands_in_workspace(self):
        tasks = json.loads((ROOT / '.vscode/tasks.json').read_text())['tasks']
        actual = {task['label']: task for task in tasks}
        for script in ('build:dev', 'check:authoring'):
            task = actual[script]
            self.assertEqual(task['type'], 'process')
            self.assertEqual(task['command'], 'bun')
            self.assertEqual(task['args'], ['run', script])
            self.assertEqual(task['options']['cwd'], '${workspaceFolder}')
            self.assertNotIn('runOptions', task, 'tasks must not run when the folder opens')
            self.assertFalse(task.get('isBackground', False))


if __name__ == '__main__':
    unittest.main()
