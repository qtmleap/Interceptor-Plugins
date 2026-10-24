"""Interceptor.createFile({storage, atPath, contents}): schema 2 `write.files` grant, compiler rules and the Salmon Run Plugin 1.2.0 contract."""
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
  await Interceptor.createFile({storage: Interceptor.Storage.iCloudDrive, atPath: 'Salmon Run/history.json', contents: JSON.stringify(res.body)});
}}});
'''
OPTS = "{storage: Interceptor.Storage.iCloudDrive, atPath: 'a/b.json', contents: %s}"


class CreateFileManifestTests(unittest.TestCase):
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


class CreateFileCompilerTests(Case):
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
        self.assertIn('Interceptor.createFile(', emitted)
        self.assertIn('Interceptor.Storage.iCloudDrive', emitted)

    def test_call_forms_that_return_the_promise_are_accepted(self):
        o = OPTS % "'{}'"
        self.accepts("Interceptor.attach({response: {async onLeave(res, cfg) { await Interceptor.createFile(%s); }}});" % o, 'method')
        self.accepts("Interceptor.attach({response: {onLeave(res, cfg) { void Interceptor.createFile(%s); }}});" % o, 'void')

    def test_usage_requires_files_true(self):
        self.rejects(SAVE, 'false', files=False)
        self.rejects(SAVE, 'undeclared', declare=False)

    def test_granted_but_unused_is_still_valid(self):
        self.accepts("Interceptor.attach({response: {onLeave(res, cfg) {}}});", 'unused')

    def test_only_a_direct_reference_inside_registered_response_on_leave(self):
        o = OPTS % "'{}'"
        body = lambda text: "Interceptor.attach({response: {onLeave: async (res, cfg) => { " + text + " }}});"
        for index, source in enumerate((
            "Interceptor.createFile(%s);\nInterceptor.attach({response: {onLeave(res, cfg) {}}});" % o,
            "Interceptor.attach({request: {onEnter(req, cfg) { void Interceptor.createFile(%s); }}});" % o,
            "Interceptor.attach({request: {onLeave(req, cfg) { void Interceptor.createFile(%s); }}});" % o,
            "Interceptor.attach({response: {onEnter(res, cfg) { void Interceptor.createFile(%s); }}});" % o,
            "async function helper() { await Interceptor.createFile(%s); }\n"
            "Interceptor.attach({response: {onLeave(res, cfg) { void helper(); }}});" % o,
            body("const make = Interceptor.createFile; await make(%s);" % o),
            body("const {createFile} = Interceptor; await createFile(%s);" % o),
            body("await Interceptor['createFile'](%s);" % o),
            body("await Interceptor.createFile.call(Interceptor, %s);" % o),
            body("await (Interceptor.createFile)(%s);" % o),
            body("await globalThis.Interceptor.createFile(%s);" % o),
            body("const i = Interceptor; await i.createFile(%s);" % o),
            body("void [Interceptor.createFile];"),
            body("await createFile(%s);" % o),
            body("const i = Interceptor; await Interceptor.createFile({storage: i.Storage.local, atPath: 'a', contents: ''});"),
            body("const {Storage} = Interceptor; await Interceptor.createFile({storage: Storage.local, atPath: 'a', contents: ''});"),
            body("const S = Interceptor.Storage; await Interceptor.createFile({storage: S.local, atPath: 'a', contents: ''});"),
            body("await Interceptor.createFile({storage: globalThis.Interceptor.Storage.local, atPath: 'a', contents: ''});"),
            body("const Interceptor = {Storage: {local: 1}, createFile() {}} as any; await Interceptor.createFile({});"),
        )):
            with self.subTest(source=source):
                self.rejects(source, f'direct-{index}')

    def test_old_save_json_alias_is_unsupported(self):
        for index, text in enumerate(("await Interceptor.saveJSON('k', '{}');", "await Interceptor['saveJSON']('k', '{}');",
                                      "const f = Interceptor.saveJSON; void f;")):
            with self.subTest(text=text):
                self.rejects("Interceptor.attach({response: {onLeave: async (res, cfg) => { " + text + " }}});", f'old-{index}')

    def test_storage_cases_are_allowed_in_constants_types_and_callbacks(self):
        self.accepts("const ROOT = Interceptor.Storage.iCloudDrive;\n"
                     "const other: Interceptor.Storage = Interceptor.Storage.local;\n"
                     "type Where = typeof Interceptor.Storage;\n"
                     "Interceptor.attach({response: {onLeave: async (res, cfg) => {\n"
                     "  await Interceptor.createFile({storage: ROOT, atPath: 'a/b.json', contents: ''});\n"
                     "  void other;\n}}});\n", 'storage-forms')

    def test_contents_accept_text_csv_empty_and_binary(self):
        body = lambda text: "Interceptor.attach({response: {onLeave: async (res, cfg) => { " + text + " }}});"
        for index, contents in enumerate(("''", "'a,b\\n1,2\\n'", "'text'", "new Uint8Array([0, 1, 255])",
                                         "new Uint8Array(0)", "Uint8Array.from([0, 0])")):
            with self.subTest(contents=contents):
                self.accepts(body("await Interceptor.createFile(%s);" % (OPTS % contents)), f'contents-{index}')

    def test_only_uint8array_is_enabled_among_binary_types(self):
        body = lambda text: "Interceptor.attach({response: {onLeave: async (res, cfg) => { " + text + " }}});"
        for index, text in enumerate(("const a = new Uint16Array(1); void a;", "const a = new Int8Array(1); void a;",
                                      "const a = new Uint8ClampedArray(1); void a;", "const a = new ArrayBuffer(1); void a;",
                                      "const a = new SharedArrayBuffer(1); void a;", "const a = new DataView(new ArrayBuffer(1)); void a;",
                                      "Atomics.load(new Int32Array(1), 0);")):
            with self.subTest(text=text):
                self.rejects(body(text), f'binary-{index}')
        # Uint8Array is not a general host global: only inside a response.onLeave callback.
        self.rejects("const bytes = new Uint8Array(1);\nInterceptor.attach({response: {onLeave(res, cfg) {}}});", 'top-level-bytes')
        self.rejects("Interceptor.attach({request: {onEnter(req, cfg) { const a = new Uint8Array(1); void a; }}});", 'enter-bytes')

    def test_signature_is_typed_options_returning_promise_void(self):
        body = lambda text: "Interceptor.attach({response: {onLeave: async (res, cfg) => { " + text + " }}});"
        S = 'Interceptor.Storage.iCloudDrive'
        for index, source in enumerate((
            body("await Interceptor.createFile();"),
            body("await Interceptor.createFile('a', 'b');"),
            body("await Interceptor.createFile({storage: 'icloud', atPath: 'a', contents: ''});"),
            body("await Interceptor.createFile({storage: 'local', atPath: 'a', contents: ''});"),
            body("await Interceptor.createFile({atPath: 'a', contents: ''});"),
            body("await Interceptor.createFile({storage: %s, contents: ''});" % S),
            body("await Interceptor.createFile({storage: %s, atPath: 'a'});" % S),
            body("await Interceptor.createFile({storage: %s, atPath: 1, contents: ''});" % S),
            body("await Interceptor.createFile({storage: %s, atPath: 'a', contents: {}});" % S),
            body("await Interceptor.createFile({storage: %s, atPath: 'a', contents: 1});" % S),
            body("await Interceptor.createFile({storage: %s, atPath: 'a', contents: [1]});" % S),
            body("await Interceptor.createFile({storage: %s, atPath: 'a', contents: '', extra: 1});" % S),
            body("await Interceptor.createFile({storage: %s, atPath: 'a', contents: ''}, 1);" % S),
            body("const n: string = await Interceptor.createFile({storage: %s, atPath: 'a', contents: ''}); void n;" % S),
        )):
            with self.subTest(source=source):
                self.rejects(source, f'signature-{index}')

    def test_declaration_file_declares_create_file(self):
        text = (REPO / 'types/interceptor.d.ts').read_text()
        self.assertRegex(text, r'function createFile\(\s*options:\s*CreateFileOptions\s*\):\s*Promise<void>')
        self.assertRegex(text, r"enum Storage\s*\{\s*local\s*=\s*'local',\s*iCloudDrive\s*=\s*'icloud'\s*,?\s*\}")
        self.assertRegex(text, r'storage:\s*Storage')
        self.assertRegex(text, r'atPath:\s*string')
        self.assertRegex(text, r'contents:\s*string\s*\|\s*Uint8Array')
        self.assertNotIn('saveJSON', text)


class SalmonManifestTests(unittest.TestCase):
    def test_salmon_plugin_requests_files_write(self):
        manifest = json.loads((REPO / 'plugins/splatnet3-salmon/plugin.json').read_text())
        self.assertEqual(manifest['version'], '1.2.1')
        self.assertEqual(manifest['publishedAt'], '2026-10-24T00:00:00Z')
        self.assertIs(manifest['write']['files'], True)
        self.assertIs(manifest['write']['requestBody'], False)
        self.assertIs(manifest['write']['responseBody'], False)


if __name__ == '__main__':
    unittest.main()
