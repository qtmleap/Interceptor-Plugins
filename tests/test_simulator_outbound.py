"""Run outbound conformance through the shared C bridge; this CLI never delivers requests."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get('INTERCEPTOR_SIMULATOR', ROOT / '.tools/bin/interceptor-simulator'))
SOURCE_FILE = 'hooks/api.example.com/credentials/POST.js'
PREVIEW_ID = '5E1D0C4A-0000-4000-8000-00000000A001'
BASE = {
    'schemaVersion': 2, 'id': '3F0C9B64-5E0D-4B7A-9C1E-6A7D2B8E4F10', 'name': 'Outbound', 'version': '2.0.0',
    'matches': [{'hosts': ['api.example.com'], 'methods': ['POST'], 'path': {'kind': 'exact', 'value': '/credentials'},
                 'hooks': {'request': {'onEnter': SOURCE_FILE}}}],
    'read': {'metadata': ['method', 'host', 'path', 'status'], 'headers': [], 'queryKeys': [], 'body': {'mode': 'json'}},
    'write': {'requestBody': False, 'responseBody': False}, 'endpointBindings': ['preview'], 'settings': {},
    'outbound': {'lookup': {'url': 'https://api.example.com/profile', 'method': 'GET', 'headers': ['authorization', 'cookie', 'accept']}},
}
EVENT = {
    'phase': 'request.onEnter',
    'request': {'method': 'POST', 'host': 'api.example.com', 'path': '/credentials', 'body': {'ok': True}},
    'response': {'status': 200, 'body': {'accessToken': 'interceptor-test-token'}},
}


class SimulatorOutboundTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(BINARY.is_file(), 'build the Rust simulator against the reviewed outbound C bridge')
        self.temporary = tempfile.TemporaryDirectory(prefix='sim-outbound-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def run_package(self, body='', manifest=None, phase='request.onEnter', source=None):
        metadata = copy.deepcopy(BASE if manifest is None else manifest)
        leg, callback = phase.split('.')
        metadata['matches'][0]['hooks'] = {leg: {callback: SOURCE_FILE}}
        package = {'manifest': metadata, 'sourceFiles': {SOURCE_FILE: source or 'Interceptor.attach({' + leg + ':{' + callback + '(){' + body + '}}});'}}
        event = dict(EVENT, phase=phase)
        paths = []
        for name, value in (('package', package), ('event', event), ('config', {'endpoints': {'preview': PREVIEW_ID}})):
            path = self.directory / (name + '.json')
            path.write_text(json.dumps(value))
            paths.append(str(path))
        return subprocess.run([str(BINARY), 'run-package', paths[0], phase, *paths[1:]], capture_output=True, timeout=10)

    def assert_rejected(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, b'')

    def test_shared_native_and_sdk_declaration_cases(self):
        cases = json.loads((ROOT / 'fixtures/outbound-conformance.json').read_text())['cases']
        for case in cases:
            with self.subTest(case=case['name']):
                result = self.run_package(manifest=dict(BASE, outbound=case['outbound']))
                if case['valid']:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), {'actions': []})
                else:
                    self.assert_rejected(result)

    def test_all_four_callbacks_collect_get_intents_for_original_post(self):
        for phase in ('request.onEnter', 'request.onLeave', 'response.onEnter', 'response.onLeave'):
            with self.subTest(phase=phase):
                result = self.run_package("Interceptor.send('lookup',{headers:{authorization:'Bearer interceptor-test-token'}});", phase=phase)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {'actions': [
                    {'type': 'http', 'binding': 'lookup', 'headers': {'authorization': 'Bearer interceptor-test-token'}},
                ]})

    def test_send_requires_two_arguments_and_required_plain_string_headers(self):
        calls = (
            "Interceptor.send('lookup');", "Interceptor.send('lookup',{});",
            "Interceptor.send('lookup',{headers:{}},{});",
            "Interceptor.send('missing',{headers:{}});",
            "Interceptor.send('lookup',{headers:[]});",
            "Interceptor.send('lookup',{headers:{other:'x'}});",
            "Interceptor.send('lookup',{headers:{authorization:1}});",
            "Interceptor.send('lookup',{headers:{authorization:'x\\r\\ny'}});",
            "Interceptor.send('lookup',{headers:{authorization:'é'}});",
            "Interceptor.send('lookup',{headers:{},url:'https://other.example.com/'});",
        )
        for call in calls:
            with self.subTest(call=call):
                self.assert_rejected(self.run_package('try {' + call + '} catch (error) {}'))
        accepted = self.run_package("Interceptor.send('lookup',{headers:{}});")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout), {'actions': [{'type': 'http', 'binding': 'lookup', 'headers': {}}]})

    def test_registration_calls_and_caught_later_errors_discard_all_intents(self):
        self.assert_rejected(self.run_package(source="try { Interceptor.send('lookup',{headers:{}}); } catch (error) {} Interceptor.attach({request:{onEnter(){}}});"))
        self.assert_rejected(self.run_package("Interceptor.send('lookup',{headers:{}}); try { Interceptor.send('missing',{headers:{}}); } catch (error) {}"))
        self.assert_rejected(self.run_package("Interceptor.send('lookup',{headers:{}}); throw new Error('later');"))

    def test_header_limits_and_combined_action_limit(self):
        accepted = self.run_package("Interceptor.send('lookup',{headers:{authorization:'a'.repeat(4096),cookie:'b'.repeat(4096)}});")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(len(json.loads(accepted.stdout)['actions'][0]['headers']['cookie']), 4096)
        for body in (
            "Interceptor.send('lookup',{headers:{authorization:'a'.repeat(4097)}});",
            "Interceptor.send('lookup',{headers:{authorization:'a'.repeat(4096),cookie:'b'.repeat(4096),accept:'c'}});",
            "Interceptor.send('lookup',{headers:{}}); Interceptor.send('lookup',{headers:{}}); Interceptor.send('lookup',{headers:{}});",
            "Interceptor.send('lookup',{headers:{}}); return {actions:[{type:'webhook',endpointId:'" + PREVIEW_ID + "',json:{}},{type:'webhook',endpointId:'" + PREVIEW_ID + "',json:{}}]};",
        ):
            with self.subTest(body=body):
                self.assert_rejected(self.run_package(body))

        mixed = self.run_package("Interceptor.send('lookup',{headers:{}}); return {actions:[{type:'webhook',endpointId:'" + PREVIEW_ID + "',json:{}}]};")
        self.assertEqual(mixed.returncode, 0, mixed.stderr)
        self.assertEqual(len(json.loads(mixed.stdout)['actions']), 2)

    def test_old_packages_do_not_gain_outbound_access(self):
        manifest = copy.deepcopy(BASE)
        del manifest['outbound']
        unchanged = self.run_package(manifest=manifest)
        self.assertEqual(unchanged.returncode, 0, unchanged.stderr)
        self.assertEqual(json.loads(unchanged.stdout), {'actions': []})
        self.assert_rejected(self.run_package("Interceptor.send('lookup',{headers:{}});", manifest=manifest))
        source = self.directory / 'legacy.js'
        source.write_text("function onRequest(){ Interceptor.send('lookup',{headers:{}}); return {actions:[]}; }")
        event, config = self.directory / 'legacy-event.json', self.directory / 'legacy-config.json'
        event.write_text('{}'); config.write_text('{}')
        result = subprocess.run([str(BINARY), 'run', str(source), 'onRequest', str(event), str(config)], capture_output=True, timeout=10)
        self.assert_rejected(result)

    def test_two_collected_intents_are_reported_in_order(self):
        result = self.run_package("Interceptor.send('lookup',{headers:{authorization:'first'}}); Interceptor.send('lookup',{headers:{cookie:'second'}});")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'actions': [
            {'type': 'http', 'binding': 'lookup', 'headers': {'authorization': 'first'}},
            {'type': 'http', 'binding': 'lookup', 'headers': {'cookie': 'second'}},
        ]})
