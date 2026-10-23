"""Async fetch is available only inside a schema 2 response.onLeave callback."""
import json
import shutil

from helpers import Case, REPO, OFFICIAL_PLUGIN_IDS

LEAVE = '''Interceptor.attach({response: {onLeave: async (res, cfg) => {
  const reply = await fetch('https://example.com/a', {method: 'POST', headers: {a: 'b'}, body: '{}'});
  if (!reply.ok || reply.status !== 200) return;
  const data = await reply.json();
  const text: string = await reply.text();
  async function helper(): Promise<number> { const r = await fetch('https://example.com/b'); return r.status; }
  const nested = async () => (await fetch('https://example.com/c', {method: 'GET'})).ok;
  void [data, text, helper, nested];
}}});
'''


class CompilerFetchTests(Case):
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
        return root

    def build(self, source, name):
        root = self.routed_root()
        (root / 'plugins/demo/hooks/example.com').mkdir()
        (root / 'plugins/demo/hooks/example.com/GET.ts').write_text(source)
        out = self.tmp / name
        return self.run_tool(root, 'build', '--output', out), out

    def accepts(self, source, name='ok'):
        result, out = self.build(source, name)
        self.ok(result)
        return json.loads((out / 'plugins/demo.json').read_text())['sourceFiles']['hooks/example.com/GET.js']

    def rejects(self, source, name='bad'):
        result, out = self.build(source, name)
        self.fails(result)
        self.assertFalse(out.exists())

    def test_leave_callback_may_await_fetch_including_nested_helpers(self):
        emitted = self.accepts(LEAVE)
        self.assertIn('async', emitted)
        self.assertIn('await fetch(', emitted)

    def test_async_method_form_and_sync_leave_are_accepted(self):
        self.accepts("Interceptor.attach({response: {async onLeave(res, cfg) { await fetch('https://example.com'); }}});")
        self.accepts("Interceptor.attach({response: {onLeave(res, cfg) { void fetch('https://example.com'); }}});", 'sync')

    def test_async_and_await_stay_rejected_outside_response_leave(self):
        for index, source in enumerate((
            "Interceptor.attach({request: {onEnter: async (req, cfg) => { await 1; }}});",
            "Interceptor.attach({request: {async onLeave(req, cfg) {}}});",
            "Interceptor.attach({response: {onEnter: async (res, cfg) => {}}});",
            "async function helper() {}\nInterceptor.attach({response: {onLeave(res, cfg) { void helper(); }}});",
            "Interceptor.attach({response: {onLeave: async function* (res, cfg) {}}});",
            "Interceptor.attach({response: {onLeave: async (res, cfg) => { for await (const x of []) { void x; } }}});",
            "Interceptor.attach({response: {onLeave(res, cfg) { Promise.resolve(1); }}});",
        )):
            with self.subTest(source=source):
                self.rejects(source, f'async-{index}')

    def test_fetch_rejected_outside_response_leave(self):
        for index, source in enumerate((
            "fetch('https://example.com');\nInterceptor.attach({response: {onLeave(res, cfg) {}}});",
            "function helper() { return fetch('https://example.com'); }\nInterceptor.attach({response: {onLeave(res, cfg) { void helper(); }}});",
            "Interceptor.attach({request: {onEnter(req, cfg) { void fetch('https://example.com'); }}});",
            "Interceptor.attach({request: {onLeave(req, cfg) { void fetch('https://example.com'); }}});",
            "Interceptor.attach({response: {onEnter(res, cfg) { void fetch('https://example.com'); }}});",
        )):
            with self.subTest(source=source):
                self.rejects(source, f'phase-{index}')

    def test_fetch_cannot_be_aliased_shadowed_or_reached_through_globals(self):
        body = lambda text: "Interceptor.attach({response: {onLeave: async (res, cfg) => { " + text + " }}});"
        for index, source in enumerate((
            body("const f = fetch; await f('https://example.com');"),
            body("const {fetch: f} = {fetch}; await f('https://example.com');"),
            body("await globalThis.fetch('https://example.com');"),
            body("await globalThis['fetch']('https://example.com');"),
            body("await fetch.call(undefined, 'https://example.com');"),
            body("await (fetch)('https://example.com');"),
            body("const fetch = (u: string) => u; fetch('x');"),
            body("const run = (fetch: string) => fetch; run('x');"),
            body("function fetch() {} fetch();"),
            body("void [fetch];"),
            body("new (fetch as any)('x');"),
            "Interceptor.attach({response: {onLeave(res, cfg) { void fetch('https://example.com'); }}});\nconst alias = fetch;",
        )):
            with self.subTest(source=source):
                self.rejects(source, f'alias-{index}')

    def test_unrelated_property_names_called_fetch_remain_allowed(self):
        self.accepts("Interceptor.attach({response: {onLeave(res, cfg) { const o = {fetch: 1}; void o.fetch; }}});")

    def test_fetch_signature_is_enforced(self):
        body = lambda text: "Interceptor.attach({response: {onLeave: async (res, cfg) => { " + text + " }}});"
        for index, source in enumerate((
            body("await fetch(1);"),
            body("await fetch('x', {method: 'DELETE'});"),
            body("await fetch('x', {headers: {a: 1}});"),
            body("await fetch('x', {body: {}});"),
            body("const n: string = (await fetch('x')).status; void n;"),
            body("await fetch('x', {credentials: 'include'});"),
        )):
            with self.subTest(source=source):
                self.rejects(source, f'signature-{index}')

    def test_other_phases_cannot_return_promises_and_hosts_stay_banned(self):
        for index, source in enumerate((
            "Interceptor.attach({response: {onEnter: (res, cfg) => Promise.resolve()}});",
            "import x from './x';\n" + LEAVE,
            "export const x = 1;\n" + LEAVE,
            LEAVE + "const g = globalThis;",
            LEAVE + "setTimeout(() => {}, 1);",
        )):
            with self.subTest(source=source):
                self.rejects(source, f'misc-{index}')
