"""Interceptor.saveJSON(key, jsonText): schema 2 `write.files` grant, compiler rules and the Salmon Run Plugin 1.1.0 contract.

These tests define the feature before it exists; they are expected to fail until it is implemented.
"""
import copy
import json
import shutil
import sys
import unittest

from helpers import Case, REPO, OFFICIAL_PLUGIN_IDS
sys.path.insert(0, str(REPO / 'tools'))
import repository_config as config

BASE = {
    'schemaVersion': 2,
    'id': '90A213C0-9D3C-47F5-ABB8-C15C7472E2AE',
    'name': 'Saver',
    'version': '1.0.0',
    'matches': [{'hosts': ['api.example.com'], 'methods': ['POST'], 'path': {'kind': 'exact', 'value': '/search'},
                 'hooks': {'response': {'onLeave': 'hooks/api.example.com/search/POST.js'}}}],
    'read': {'metadata': ['host'], 'headers': [], 'queryKeys': [], 'body': {'mode': 'json'}},
    'write': {'requestBody': False, 'responseBody': False},
    'endpointBindings': [],
    'settings': {},
}


def manifest(**write):
    value = copy.deepcopy(BASE)
    value['write'].update(write)
    return value


SAVE = '''Interceptor.attach({response: {onLeave: async (res, cfg) => {
  await Interceptor.saveJSON('key', JSON.stringify(res.body));
}}});
'''


class SaveJSONManifestTests(unittest.TestCase):
    def rejects(self, value):
        with self.assertRaises(config.ToolError):
            config.validate_manifest(value, 'manifest')

    def test_files_is_optional_and_must_be_boolean(self):
        config.validate_manifest(manifest(), 'manifest')
        config.validate_manifest(manifest(files=False), 'manifest')
        config.validate_manifest(manifest(files=True), 'manifest')
        for bad in (1, 0, 'true', None, [], {}):
            with self.subTest(files=bad):
                self.rejects(manifest(files=bad))

    def test_unknown_write_grants_stay_rejected(self):
        self.rejects(manifest(files=True, network=True))

    def test_schema_1_rejects_files(self):
        legacy = {'schemaVersion': 1, 'id': BASE['id'], 'name': 'Legacy', 'version': '1.0.0',
                  'subscriptions': [{'phase': 'request.completed', 'match': {'hosts': ['example.com']}}],
                  'read': {'metadata': ['host'], 'headers': [], 'queryKeys': [], 'body': {'mode': 'none'}},
                  'endpointBindings': ['preview'], 'settings': {}}
        config.validate_manifest(legacy, 'manifest')
        self.rejects(dict(legacy, write={'files': True}))
        self.rejects(dict(legacy, write={'requestBody': False, 'responseBody': False, 'files': True}))


class SaveJSONCompilerTests(Case):
    def build(self, source, name, files=True, declare=True):
        root = self.make_root()
        shutil.rmtree(root / 'manifests')
        shutil.rmtree(root / 'scripts')
        (root / 'plugins/demo/hooks/example.com').mkdir(parents=True)
        write = {'requestBody': True, 'responseBody': True}
        if declare:
            write['files'] = files
        meta = {'schemaVersion': 2, 'id': OFFICIAL_PLUGIN_IDS[0], 'name': 'Routes', 'version': '2.0.0',
                'read': {'metadata': ['method', 'host', 'path'], 'headers': [], 'queryKeys': [], 'body': {'mode': 'json'}},
                'write': write, 'endpointBindings': [], 'settings': {}}
        (root / 'plugins/demo/plugin.json').write_text(json.dumps(meta))
        (root / 'types').mkdir()
        shutil.copy(REPO / 'types/interceptor.d.ts', root / 'types')
        shutil.copy(REPO / 'tools/compile.mjs', root / 'tools')
        (root / 'node_modules').symlink_to(REPO / 'node_modules', target_is_directory=True)
        (root / 'plugins/demo/hooks/example.com/GET.ts').write_text(source)
        out = self.tmp / name
        return self.run_tool(root, 'build', '--output', out), out

    def accepts(self, source, name='ok'):
        result, out = self.build(source, name)
        self.ok(result)
        return json.loads((out / 'plugins/demo.json').read_text())

    def rejects(self, source, name='bad', **kwargs):
        result, out = self.build(source, name, **kwargs)
        self.fails(result)
        self.assertFalse(out.exists())

    def test_direct_awaited_call_in_response_leave_compiles_with_grant(self):
        package = self.accepts(SAVE)
        self.assertIs(package['manifest']['write']['files'], True)
        emitted = package['sourceFiles']['hooks/example.com/GET.js']
        self.assertIn('Interceptor.saveJSON(', emitted)

    def test_call_forms_that_return_the_promise_are_accepted(self):
        self.accepts("Interceptor.attach({response: {async onLeave(res, cfg) { await Interceptor.saveJSON('k', '{}'); }}});", 'method')
        self.accepts("Interceptor.attach({response: {onLeave(res, cfg) { void Interceptor.saveJSON('k', '{}'); }}});", 'void')

    def test_usage_requires_files_true(self):
        self.rejects(SAVE, 'false', files=False)
        self.rejects(SAVE, 'undeclared', declare=False)

    def test_granted_but_unused_is_still_valid(self):
        self.accepts("Interceptor.attach({response: {onLeave(res, cfg) {}}});", 'unused')

    def test_only_a_direct_reference_inside_registered_response_on_leave(self):
        body = lambda text: "Interceptor.attach({response: {onLeave: async (res, cfg) => { " + text + " }}});"
        for index, source in enumerate((
            "Interceptor.saveJSON('k', '{}');\nInterceptor.attach({response: {onLeave(res, cfg) {}}});",
            "Interceptor.attach({request: {onEnter(req, cfg) { void Interceptor.saveJSON('k', '{}'); }}});",
            "Interceptor.attach({request: {onLeave(req, cfg) { void Interceptor.saveJSON('k', '{}'); }}});",
            "Interceptor.attach({response: {onEnter(res, cfg) { void Interceptor.saveJSON('k', '{}'); }}});",
            "async function helper() { await Interceptor.saveJSON('k', '{}'); }\n"
            "Interceptor.attach({response: {onLeave(res, cfg) { void helper(); }}});",
            body("const save = Interceptor.saveJSON; await save('k', '{}');"),
            body("const {saveJSON} = Interceptor; await saveJSON('k', '{}');"),
            body("await Interceptor['saveJSON']('k', '{}');"),
            body("await Interceptor.saveJSON.call(Interceptor, 'k', '{}');"),
            body("await (Interceptor.saveJSON)('k', '{}');"),
            body("await globalThis.Interceptor.saveJSON('k', '{}');"),
            body("const i = Interceptor; await i.saveJSON('k', '{}');"),
            body("void [Interceptor.saveJSON];"),
            body("await saveJSON('k', '{}');"),
        )):
            with self.subTest(source=source):
                self.rejects(source, f'direct-{index}')

    def test_signature_is_key_string_json_string_returning_promise_void(self):
        body = lambda text: "Interceptor.attach({response: {onLeave: async (res, cfg) => { " + text + " }}});"
        for index, source in enumerate((
            body("await Interceptor.saveJSON('k');"),
            body("await Interceptor.saveJSON(1, '{}');"),
            body("await Interceptor.saveJSON('k', {});"),
            body("await Interceptor.saveJSON('k', '{}', 1);"),
            body("const n: string = await Interceptor.saveJSON('k', '{}'); void n;"),
        )):
            with self.subTest(source=source):
                self.rejects(source, f'signature-{index}')

    def test_declaration_file_declares_save_json(self):
        text = (REPO / 'types/interceptor.d.ts').read_text()
        self.assertRegex(text, r'saveJSON\(\s*key:\s*string,\s*\w+:\s*string\s*\):\s*Promise<void>')


class SalmonManifestTests(unittest.TestCase):
    def test_plugin_1_1_0_requests_files_write(self):
        manifest = json.loads((REPO / 'plugins/splatnet3-salmon/plugin.json').read_text())
        self.assertEqual(manifest['version'], '1.1.0')
        self.assertIs(manifest['write']['files'], True)
        self.assertIs(manifest['write']['requestBody'], False)
        self.assertIs(manifest['write']['responseBody'], False)


if __name__ == '__main__':
    unittest.main()
