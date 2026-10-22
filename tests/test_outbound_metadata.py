"""Optional schema 2 `outbound` metadata: validation, authored pass-through and generated manifests."""
import copy
import json
import shutil
import subprocess
import sys

from helpers import REPO
import test_filesystem_hooks
sys.path.insert(0, str(REPO / 'tools'))
import repository_config as config
import route_sources

from helpers import Case

BASE = {
    'schemaVersion': 2, 'id': '90A213C0-9D3C-47F5-ABB8-C15C7472E2AE', 'name': 'Outbound', 'version': '2.0.0',
    'matches': [{'hosts': ['example.com'], 'methods': ['GET'], 'path': {'kind': 'exact', 'value': '/'},
                 'hooks': {'request': {'onEnter': 'hooks/example.com/GET.js'}}}],
    'read': {'metadata': ['host'], 'headers': [], 'queryKeys': [], 'body': {'mode': 'none'}},
    'write': {'requestBody': False, 'responseBody': False},
    'endpointBindings': [], 'settings': {},
}


def decl(url='https://api.example.com/v1/items', headers=(), **extra):
    return dict({'url': url, 'method': 'GET', 'headers': list(headers)}, **extra)


def manifest(outbound, schema=2):
    value = copy.deepcopy(BASE)
    value['outbound'] = outbound
    if schema == 1:
        del value['matches'], value['write']
        value['schemaVersion'] = 1
        value['subscriptions'] = [{'phase': 'request.completed', 'match': {'hosts': ['example.com']}}]
    return value


class OutboundMetadataTests(Case):
    def accepts(self, outbound):
        config.validate_manifest(manifest(outbound), 'manifest')

    def rejects(self, outbound):
        with self.assertRaises(config.ToolError):
            config.validate_manifest(manifest(outbound), 'manifest')

    def test_shared_native_and_sdk_conformance_cases(self):
        cases = json.loads((REPO / 'fixtures/outbound-conformance.json').read_text())['cases']
        for case in cases:
            with self.subTest(case=case['name']):
                (self.accepts if case['valid'] else self.rejects)(case['outbound'])

    def test_accepts_empty_and_valid_declarations(self):
        self.accepts({})
        self.accepts({'Lookup_1': decl(), 'b': decl('https://a-b.example.co.uk/%41%2f%e3?'.rstrip('?'), ['accept', 'x-api-key'])})
        self.accepts({'a': decl('https://example.com/')})
        self.accepts({'a': decl('https://xn--abc.example.com/Mixed/Case')})
        self.accepts({'a': decl('https://example.1a/')})
        self.accepts({k: decl() for k in 'abcd'})
        self.accepts({'a' + 'b' * 31: decl()})
        # independent from the four-entry endpointBindings budget
        value = manifest({k: decl() for k in 'abcd'})
        value['endpointBindings'] = ['one', 'two', 'three', 'four']
        config.validate_manifest(value, 'manifest')

    def test_absent_outbound_is_unchanged_and_schema_one_rejects_it(self):
        config.validate_manifest(copy.deepcopy(BASE), 'manifest')
        with self.assertRaises(config.ToolError):
            config.validate_manifest(manifest({}, schema=1), 'manifest')

    def test_rejects_bad_shapes_and_bindings(self):
        for outbound in (None, [], 'x', {k: decl() for k in 'abcde'}, {'1a': decl()}, {'_a': decl()},
                         {'a-b': decl()}, {'é': decl()}, {'a' * 33: decl()}, {'': decl()}):
            with self.subTest(outbound=outbound):
                self.rejects(outbound)
        for declaration in (None, [], {}, {'url': decl()['url'], 'method': 'GET'},
                            {'url': decl()['url'], 'headers': []}, decl(extra=1), decl(method='POST'),
                            decl(method='get'), dict(decl(), method=None), dict(decl(), headers={}),
                            dict(decl(), headers='accept'), dict(decl(), url=1)):
            with self.subTest(declaration=declaration):
                self.rejects({'a': declaration})

    def test_rejects_unsafe_urls(self):
        bad = ['http://example.com/', 'HTTPS://example.com/', 'https://Example.com/', 'https://example.com',
               'https://example.com:443/', 'https://example.com:8443/', 'https://example.com./',
               'https://user@example.com/', 'https://user:pw@example.com/', 'https://example.com/#f',
               'https://example.com/?q=1', 'https://example.com/a?', 'https://localhost/', 'https://printer.local/',
               'https://a.local/', 'https://a.localhost/', 'https://nested.example.localhost/',
               'https://example/', 'https://127.0.0.1/', 'https://1.2.3.4/', 'https://[::1]/',
               'https://1.2.3.4.5/', 'https://example.123/', 'https://-a.example.com/', 'https://a-.example.com/',
               'https://a..example.com/', 'https://.example.com/', 'https://exa_mple.com/', 'https://exämple.com/',
               'https://example.com/a b', 'https://example.com/a\tb', 'https://example.com/a\x7f',
               'https://example.com/\\a', 'https://example.com/ä', 'https://example.com/%', 'https://example.com/%4',
               'https://example.com/%zz', 'https://example.com/%4G', ' https://example.com/', 'https://example.com/ ',
               'https://exa mple.com/', 'https://example.com\\@evil.com/', 'https://' + 'a' * 64 + '.example.com/',
               'https://' + '.'.join(['a' * 63] * 4) + '/', 'https:///path', 'https://.com/', '']
        for url in bad:
            with self.subTest(url=url):
                self.rejects({'a': decl(url)})

    def test_path_matches_native_encoded_path_grammar(self):
        for path in ("/a-._~!$&'()*+,;=:@/b", '/%41%2f%e3%E3%7e%20', '/%80%ff', '/a/'):
            with self.subTest(path=path):
                self.accepts({'a': decl('https://example.com' + path)})
        controls = ['%%%02x' % n for n in range(0x20)] + ['%7f', '%7F', '%5c', '%5C', '%0D', '%0a', '%00']
        literals = list('[]{}|^<>`"') + ['\\', ' ', '\x00', '\x1f', '\x7f', '\x80']
        for tail in controls + literals:
            with self.subTest(tail=tail):
                self.rejects({'a': decl('https://example.com/a' + tail)})

    def test_url_length_limits(self):
        prefix = 'https://example.com'
        self.accepts({'a': decl(prefix + '/' + 'a' * 1023)})
        self.rejects({'a': decl(prefix + '/' + 'a' * 1024)})
        self.accepts({'a': decl(prefix + '/' + '%41' * 341)})
        self.rejects({'a': decl(prefix + '/' + '%41' * 342)})
        self.rejects({'a': decl('https://' + 'a.' * 1030 + 'com/' )})
        self.rejects({'a': decl('https://example.com/' + 'a' * 2048)})

    def test_header_names(self):
        self.accepts({'a': decl(headers=['accept'])})
        self.accepts({'a': decl(headers=['x' + str(i) for i in range(8)])})
        self.accepts({'a': decl(headers=["!#$%&'*+-.^_`|~09az"])})
        self.accepts({'a': decl(headers=['a' * 128])})
        bad = [['A'], ['Accept'], [''], ['a' * 129], ['a b'], ['a:b'], [':authority'], [':path'], ['é'], ['a\n'],
               ['a', 'a'], ['x' + str(i) for i in range(9)], [1], [None], ['a(b']]
        bad += [[n] for n in ('host', 'content-length', 'transfer-encoding', 'connection', 'upgrade', 'te',
                              'trailer', 'expect', 'keep-alive', 'set-cookie', 'proxy-authorization',
                              'proxy-connection', 'proxy-', 'proxy-x')]
        for headers in bad:
            with self.subTest(headers=headers):
                self.rejects({'a': decl(headers=headers)})

    def test_authored_metadata_accepts_outbound_and_rejects_invalid(self):
        value = copy.deepcopy(BASE)
        del value['matches']
        value['outbound'] = {'lookup': decl(headers=['accept'])}
        path = self.tmp / 'plugin.json'
        path.write_text(json.dumps(value))
        self.assertEqual(route_sources.metadata(path)['outbound'], value['outbound'])
        value['outbound']['lookup']['url'] = 'http://example.com/'
        path.write_text(json.dumps(value))
        with self.assertRaises(config.ToolError):
            route_sources.metadata(path)


class OutboundBuildTests(Case):
    routed_root = test_filesystem_hooks.FilesystemHooksTests.routed_root
    route = test_filesystem_hooks.FilesystemHooksTests.route
    build = test_filesystem_hooks.FilesystemHooksTests.build

    def test_outbound_passes_unchanged_to_generated_manifest(self):
        root = self.routed_root()
        path = root / 'plugins/demo/plugin.json'
        metadata = json.loads(path.read_text())
        metadata['outbound'] = {'Lookup': decl('https://api.example.com/v1/%41', ['accept', 'x-api-key']), 'empty': decl()}
        path.write_text(json.dumps(metadata))
        self.ok(self.build(root))
        package = json.loads((self.tmp / 'out/plugins/demo.json').read_text())
        self.assertEqual(package['manifest']['outbound'], metadata['outbound'])

    def test_invalid_outbound_fails_the_build(self):
        root = self.routed_root()
        path = root / 'plugins/demo/plugin.json'
        metadata = json.loads(path.read_text())
        metadata['outbound'] = {'a': decl('http://api.example.com/')}
        path.write_text(json.dumps(metadata))
        self.assertNotEqual(self.build(root).returncode, 0)

    def test_real_example_builds_and_extracts_public_fixture_credentials(self):
        root = self.routed_root()
        shutil.rmtree(root / 'plugins/demo')
        shutil.copytree(REPO / 'fixtures/outbound-example', root / 'plugins/demo')
        self.ok(self.build(root))
        path = self.tmp / 'out/plugins/demo.json'
        package = json.loads(path.read_text())
        host = 'interceptor-traffic-fixture.lemonandchan.workers.dev'
        source_file = 'hooks/' + host + '/auth/credentials/GET.js'
        self.assertEqual(package['manifest']['matches'], [{
            'hosts': [host], 'methods': ['GET'], 'path': {'kind': 'exact', 'value': '/auth/credentials'},
            'hooks': {'response': {'onLeave': source_file}},
        }])
        self.assertEqual(package['manifest']['outbound'], {
            'bearer': decl('https://' + host + '/auth/bearer', ['authorization']),
            'cookie': decl('https://' + host + '/auth/cookie', ['cookie']),
        })
        self.assertEqual(package['manifest']['read']['headers'], ['set-cookie'])
        # Execute the compiled example against the public fixture's documented response.
        # This checks extraction only; the stand-in records intents and makes no network calls.
        script = '''
const pkg = JSON.parse(await Bun.file(process.argv[1]).text());
const host = {actions: [], attach(hooks) { host.hooks = hooks; }, send(binding, options) { host.actions.push({type: 'http', binding, ...options}); }};
globalThis.Interceptor = host;
eval(Object.values(pkg.sourceFiles)[0]);
const cases = [
  {status: 200, body: {accessToken: 'interceptor-test-token', tokenType: 'Bearer'},
    headers: {'set-cookie': 'fixture_session=dummy-session-not-a-secret; Path=/; Secure; HttpOnly; SameSite=Lax'}},
  {status: 200, body: {accessToken: 'another-token'}, headers: {'set-cookie': 'fixture_session=another-session; Path=/'}},
  {status: 200, body: {token: 'old-field'}, headers: {'set-cookie': 'fixture_session=unused'}},
  {status: 401, body: {accessToken: 'unused'}, headers: {'set-cookie': 'fixture_session=unused'}},
  {status: 200, body: {accessToken: 'valid-token'}, headers: {}},
];
console.log(JSON.stringify(cases.map(response => {
  host.actions = [];
  host.hooks.response.onLeave({...response, request: {}}, {});
  return host.actions;
})));
'''
        result = subprocess.run(['bun', '--eval', script, str(path)], capture_output=True, text=True, timeout=30)
        self.ok(result)
        self.assertEqual(json.loads(result.stdout), [
            [{'type': 'http', 'binding': 'bearer', 'headers': {'authorization': 'Bearer interceptor-test-token'}},
             {'type': 'http', 'binding': 'cookie', 'headers': {'cookie': 'fixture_session=dummy-session-not-a-secret'}}],
            [{'type': 'http', 'binding': 'bearer', 'headers': {'authorization': 'Bearer another-token'}},
             {'type': 'http', 'binding': 'cookie', 'headers': {'cookie': 'fixture_session=another-session'}}],
            [], [], [{'type': 'http', 'binding': 'bearer', 'headers': {'authorization': 'Bearer valid-token'}}],
        ])
