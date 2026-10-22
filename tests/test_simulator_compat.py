"""Runtime-facing simulator CLI cases for schema 2 (`run-package`) plus the preserved schema 1 conformance suite.

Needs the Rust simulator built against the new pin (tools/build-runtime.sh); skipped-free on purpose: a missing binary fails.
Cases whose exact exit status belongs to the C runtime assert only "rejected" (non-zero, no stdout result).
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get('INTERCEPTOR_SIMULATOR', ROOT / '.tools/bin/interceptor-simulator'))
sys.path.insert(0, str(ROOT / 'tools'))

ENTER = 'request.onEnter'
SOURCE = """
Interceptor.attach({
  request: { onEnter(request) { request.body.limit = 5; } }
});
"""
LEAVE_MUTATES = SOURCE.replace('onEnter', 'onLeave')


class SimulatorCompatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from repository_config import load_samples
        cls.samples = {name: {'manifest': manifest, 'sourceFiles': files} for name, manifest, files in load_samples(ROOT)}

    def setUp(self):
        self.assertTrue(BINARY.is_file(), 'build the Rust simulator with tools/build-runtime.sh')
        self.dir = Path(tempfile.mkdtemp(prefix='sim-compat-'))
        self.addCleanup(lambda: __import__('shutil').rmtree(self.dir, ignore_errors=True))
        self.manifest = copy.deepcopy(self.samples['request-summary']['manifest'])
        self.file = next(iter(self.manifest['matches'][0]['hooks']['request'].values()))
        self.manifest['matches'][0]['hooks'] = {'request': {'onEnter': self.file}}
        self.event = json.loads((ROOT / 'fixtures/request-event.json').read_text())
        self.config = json.loads((ROOT / 'fixtures/config.json').read_text())

    def write(self, name, value):
        path = self.dir / name
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        return path

    def run_v2(self, source=SOURCE, phase=ENTER, event=None, manifest=None, package_path=None, config=None, files=None):
        manifest = self.manifest if manifest is None else manifest
        package = {'manifest': manifest, 'sourceFiles': {self.file: source} if files is None else files}
        args = [package_path or self.write('p.json', package), phase,
                self.write('e.json', self.event if event is None else event),
                self.write('c.json', self.config if config is None else config)]
        return subprocess.run([str(BINARY), 'run-package', *map(str, args)], capture_output=True, timeout=10)

    def assertRejected(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, b'')

    def test_fixture_event_is_the_v2_search_request(self):
        self.assertEqual(self.event['phase'], ENTER)
        self.assertEqual(self.event['request'], {'method': 'POST', 'host': 'api.example.com', 'path': '/search',
                                                 'body': {'query': 'x', 'limit': 50}})

    def test_matching_request_is_mutated(self):
        result = self.run_v2()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'actions': [], 'mutation': {'body': {'query': 'x', 'limit': 5}}})

    def test_non_matching_request_is_untouched(self):
        for key, value in (('host', 'other.example.com'), ('path', '/other'), ('method', 'GET')):
            with self.subTest(key=key):
                event = copy.deepcopy(self.event)
                event['request'][key] = value
                result = self.run_v2(event=event)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {'actions': []})

    def test_phase_without_registration_is_a_no_op(self):
        event = copy.deepcopy(self.event)
        event['phase'] = 'request.onLeave'
        result = self.run_v2(phase='request.onLeave', event=event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'actions': []})

    def test_missing_package_file_is_a_usage_error(self):
        result = self.run_v2(package_path=self.dir / 'absent.json')
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertEqual(result.stdout, b'')

    def test_package_must_be_a_strict_json_object(self):
        for text in ('', '[]', '1', 'null', '{"a":1,"a":2}', '{"a":'):
            with self.subTest(text=text):
                self.assertEqual(self.run_v2(package_path=self.write('bad.json', text)).returncode, 4)

    def test_invalid_manifest_content_is_rejected(self):
        broken = {k: v for k, v in self.manifest.items() if k != 'matches'}
        self.assertRejected(self.run_v2(manifest=broken))
        self.assertRejected(self.run_v2(manifest=dict(self.manifest, schemaVersion=3)))
        self.assertRejected(self.run_v2(manifest=dict(self.manifest, matches=[])))

    def test_unknown_phase_and_legacy_hook_with_package_are_usage_errors(self):
        for phase in ('request.completed', 'onRequest', 'request.onenter', ''):
            with self.subTest(phase=phase):
                self.assertEqual(self.run_v2(phase=phase).returncode, 4)

    def test_phase_not_declared_readable_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['read']['body'] = {'mode': 'none'}
        self.assertRejected(self.run_v2(manifest=manifest))

    def test_write_without_declared_permission_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['write'] = {'requestBody': False, 'responseBody': False}
        self.assertRejected(self.run_v2(manifest=manifest))

    def test_leave_mutation_is_rejected(self):
        event = copy.deepcopy(self.event)
        event['phase'] = 'request.onLeave'
        manifest = copy.deepcopy(self.manifest)
        manifest['matches'][0]['hooks'] = {'request': {'onLeave': self.file}}
        self.assertRejected(self.run_v2(source=LEAVE_MUTATES, phase='request.onLeave', event=event, manifest=manifest))

    def test_miss_does_not_evaluate_any_source(self):
        event = copy.deepcopy(self.event)
        event['request']['host'] = 'other.example.com'
        result = self.run_v2(source='throw new Error("must not run");', event=event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'actions': []})

    def test_miss_still_validates_complete_package(self):
        event = copy.deepcopy(self.event)
        event['request']['host'] = 'other.example.com'
        for files in ({}, {self.file: SOURCE, '../bad.js': ''}, {self.file: 3}):
            with self.subTest(files=files):
                self.assertRejected(self.run_v2(files=files, event=event))

    def test_only_manifest_selected_file_runs(self):
        manifest = copy.deepcopy(self.manifest)
        route = copy.deepcopy(manifest['matches'][0])
        route['path']['value'] = '/other'
        route['hooks'] = {'request': {'onEnter': 'other.js'}}
        manifest['matches'].append(route)
        result = self.run_v2(manifest=manifest, files={self.file: SOURCE, 'other.js': 'throw new Error("must not run");'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['mutation']['body']['limit'], 5)

    def test_phase_mismatch_and_old_two_argument_attach_are_rejected(self):
        self.assertRejected(self.run_v2(source=SOURCE.replace('onEnter', 'onLeave')))
        self.assertRejected(self.run_v2(source="Interceptor.attach('search', {request:{onEnter(req){}}});"))

    def test_published_leave_samples_accept_live_empty_endpoint_map(self):
        for plugin, phase in (('request-summary', 'request.onLeave'),
                              ('request-summary', 'response.onLeave'),
                              ('server-error-filter', 'response.onLeave')):
            with self.subTest(plugin=plugin, phase=phase):
                event = copy.deepcopy(self.event)
                event['phase'] = phase
                event['response'] = {'status': 503, 'body': {'ok': True}}
                if plugin == 'server-error-filter':
                    event['request'].update(host='example.com', path='/', method='GET')
                result = self.run_v2(phase=phase, event=event, manifest=self.samples[plugin]['manifest'],
                                     files=self.samples[plugin]['sourceFiles'], config={'settings': {}, 'endpoints': {}})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {'actions': []})

    def test_v1_legacy_route_still_runs(self):
        source = self.write('v1.js', 'function onRequest(e, c) { return {actions: []}; }')
        event = self.write('v1e.json', '{}')
        result = subprocess.run([str(BINARY), 'run', str(source), 'onRequest', str(event), str(event)],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'actions': []})


class LegacyConformanceTests(unittest.TestCase):
    """The original v1 cases (base e2422ef) in fixtures/legacy-v1 run through the same engine and the explicit legacy command."""

    def setUp(self):
        os.environ.setdefault('INTERCEPTOR_SIMULATOR', str(BINARY))

    def test_preserved_files_are_schema_1(self):
        base = ROOT / 'fixtures/legacy-v1'
        for name in ('request-summary', 'server-error-filter'):
            self.assertEqual(json.loads((base / f'manifests/{name}.json').read_text())['schemaVersion'], 1)
            self.assertIn('function on', (base / f'src/{name}.js').read_text())
        cases = json.loads((base / 'cases.json').read_text())
        self.assertEqual(len(cases), 14)
        self.assertTrue(all('hook' in c and 'phase' not in c for c in cases))
        self.assertEqual(json.loads((base / 'request-event.json').read_text())['request']['method'], 'GET')

    def test_legacy_samples_library_entry_point(self):
        import repository_tool
        self.assertEqual(repository_tool.legacy_samples(ROOT), 'legacy v1 samples ok: 14 cases, 2 sources')

    def test_legacy_samples_command(self):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/repository_tool.py'), 'legacy-samples', str(ROOT)],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('legacy v1 samples ok', result.stdout)


if __name__ == '__main__':
    unittest.main()
