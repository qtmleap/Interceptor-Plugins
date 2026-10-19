"""Build real hook files into a manifest-selected package without handwritten routing."""
import json
import shutil

from helpers import Case, REPO, OFFICIAL_PLUGIN_IDS


class FilesystemHooksTests(Case):
    def routed_root(self):
        root = self.make_root()
        shutil.rmtree(root / 'manifests')
        shutil.rmtree(root / 'scripts')
        (root / 'plugins/demo/hooks').mkdir(parents=True)
        meta = {'schemaVersion': 2, 'id': OFFICIAL_PLUGIN_IDS[0], 'name': 'Routes', 'version': '2.0.0',
                'read': {'metadata': ['method', 'host', 'path'], 'headers': [], 'queryKeys': [], 'body': {'mode': 'json'}},
                'write': {'requestBody': True, 'responseBody': True}, 'endpointBindings': [], 'settings': {}}
        (root / 'plugins/demo/plugin.json').write_text(json.dumps(meta))
        (root / 'types').mkdir()
        shutil.copy(REPO / 'types/interceptor.d.ts', root / 'types')
        shutil.copy(REPO / 'tools/compile.mjs', root / 'tools')
        (root / 'node_modules').symlink_to(REPO / 'node_modules', target_is_directory=True)
        self.route(root)
        return root

    def route(self, root, route='api.example.com/search/POST.ts', source=None):
        path = root / 'plugins/demo/hooks' / route
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source or "Interceptor.attach({request:{onEnter(req,cfg){req.body.limit=5;}},response:{onEnter(res,cfg){res.body.ok=true;}}});\n")
        return path

    def build(self, root, output='out'):
        return self.run_tool(root, 'build', '--output', self.tmp / output)

    def test_path_and_callbacks_generate_manifest_and_source_files(self):
        root = self.routed_root()
        result = self.build(root)
        self.ok(result)
        package = json.loads((self.tmp / 'out/plugins/demo.json').read_text())
        self.assertEqual(set(package), {'manifest', 'sourceFiles'})
        self.assertEqual(package['manifest']['matches'], [{
            'hosts': ['api.example.com'], 'methods': ['POST'], 'path': {'kind': 'exact', 'value': '/search'},
            'hooks': {'request': {'onEnter': 'hooks/api.example.com/search/POST.js'},
                      'response': {'onEnter': 'hooks/api.example.com/search/POST.js'}}}])
        self.assertEqual(set(package['sourceFiles']), {'hooks/api.example.com/search/POST.js'})
        self.assertNotIn('api.example.com', next(iter(package['sourceFiles'].values())))
        self.assertIn('Interceptor.attach({', next(iter(package['sourceFiles'].values())))
        self.assertFalse((root / 'manifests').exists(), 'the build must not write generated routing into authored files')

    def test_root_nested_path_and_multiple_scripts_form_one_plugin(self):
        root = self.routed_root()
        self.route(root, 'api.example.com/GET.ts')
        self.route(root, 'other.example.com/v1/items/PUT.ts')
        self.ok(self.build(root))
        package = json.loads((self.tmp / 'out/plugins/demo.json').read_text())
        actual = {(m['hosts'][0], m['path']['value'], m['methods'][0]) for m in package['manifest']['matches']}
        self.assertEqual(actual, {('api.example.com', '/search', 'POST'), ('api.example.com', '/', 'GET'),
                                  ('other.example.com', '/v1/items', 'PUT')})
        self.assertEqual(len(package['sourceFiles']), 3)

    def test_generated_packages_are_deterministic(self):
        root = self.routed_root()
        self.ok(self.build(root, 'one'))
        self.ok(self.build(root, 'two'))
        self.assertEqual((self.tmp / 'one/plugins/demo.json').read_bytes(), (self.tmp / 'two/plugins/demo.json').read_bytes())

    def test_metadata_cannot_define_targets_or_file_references(self):
        for key in ('matches', 'hooks', 'sourceFiles'):
            root = self.routed_root()
            path = root / 'plugins/demo/plugin.json'
            meta = json.loads(path.read_text()); meta[key] = []
            path.write_text(json.dumps(meta))
            self.fails(self.build(root, 'invalid-' + key))

    def test_malformed_host_method_and_dynamic_routes_fail(self):
        for index, route in enumerate(('API.example.com/search/POST.ts', 'api.example.com/search/post.ts',
                                       'api.example.com/[id]/GET.ts', 'api.example.com/a%2Fb/GET.ts')):
            root = self.routed_root()
            shutil.rmtree(root / 'plugins/demo/hooks')
            (root / 'plugins/demo/hooks').mkdir()
            self.route(root, route)
            self.fails(self.build(root, 'bad-' + str(index)))

    def test_symlinked_hook_is_rejected(self):
        root = self.routed_root()
        path = root / 'plugins/demo/hooks/api.example.com/search/POST.ts'
        saved = root / 'outside.ts'; path.rename(saved); path.symlink_to(saved)
        self.fails(self.build(root))

    def test_attach_cannot_be_aliased_or_called_indirectly(self):
        direct = "Interceptor.attach({request:{onEnter(req){}}});"
        for index, extra in enumerate(("const again = Interceptor.attach; again({request:{onEnter(req){}}});",
                                       "Interceptor.attach.call(null,{request:{onEnter(req){}}});",
                                       "const host = Interceptor; host.attach({request:{onEnter(req){}}});",
                                       "Interceptor['attach']({request:{onEnter(req){}}});")):
            root = self.routed_root(); self.route(root, source=direct + extra)
            self.fails(self.build(root, 'indirect-' + str(index)))

    def test_target_arguments_are_rejected(self):
        for index, source in enumerate(("Interceptor.attach('search',{request:{onEnter(req){}}});",
                                        "Interceptor.attach({hosts:['api.example.com']},{request:{onEnter(req){}}});")):
            root = self.routed_root(); self.route(root, source=source)
            self.fails(self.build(root, 'target-' + str(index)))
