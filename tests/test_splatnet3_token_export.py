"""Run the built token-export Plugin in the shared C QuickJS bridge.

Only the host's CREATED / CREATE_ERROR reply is a fixture; the Plugin, Promise handling,
grant filtering and file-request validation are the real generated package.
"""
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SIMULATOR = Path(os.environ.get('INTERCEPTOR_SIMULATOR', str(ROOT / '.tools/bin/interceptor-simulator')))
NAME = 'splatnet3-token-export'
PACKAGE = ROOT / 'build/dev/plugins' / f'{NAME}.json'
HOOK = 'hooks/api.lp1.av5ja.srv.nintendo.net/api/bullet_tokens/POST.js'
TOKEN, VERSION, UA = 'synthetic-bullet-token-A', '99.1.0-synthetic', 'SyntheticUA/1.0 (Test)'
DEFAULT_BODY = object()


def setUpModule():
    if not SIMULATOR.is_file():
        raise RuntimeError('Run tools/build-runtime.sh before the shared QuickJS tests')
    build = subprocess.run(['bun', 'run', 'build'], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stdout + build.stderr


def exported(**fields):
    return json.dumps(fields, indent=2).encode() + b'\n'


class TokenExportTests(unittest.TestCase):
    def execute(self, *, status=201, body=DEFAULT_BODY, headers=None, create=b'CREATED\n'):
        self.assertTrue(PACKAGE.is_file(), f'missing built package {PACKAGE.relative_to(ROOT)}')
        if body is DEFAULT_BODY:
            body = {'bulletToken': TOKEN, 'lang': 'ja-JP'}
        if headers is None:
            headers = {'x-web-view-ver': VERSION, 'accept-language': 'en-US', 'user-agent': UA}
        event = {'phase': 'response.onLeave', 'request': {
            'method': 'POST', 'host': 'api.lp1.av5ja.srv.nintendo.net', 'path': '/api/bullet_tokens',
            'headers': headers}, 'response': {'status': status, 'headers': {}, 'body': body}}
        with tempfile.TemporaryDirectory(prefix='token-export-') as directory:
            event_path, config_path = f'{directory}/event.json', f'{directory}/config.json'
            Path(event_path).write_text(json.dumps(event))
            Path(config_path).write_text(json.dumps({'endpoints': {}, 'settings': {}}))
            proc = subprocess.run([str(SIMULATOR), 'run-package-fetch', str(PACKAGE), 'response.onLeave',
                                   event_path, config_path], input=create, capture_output=True, timeout=20)
        stream = io.BytesIO(proc.stdout)
        self.requests, self.saves, self.result = [], [], None
        while line := stream.readline():
            fields = line.decode().strip().split()
            self.assertIn(fields[0], ['FETCH', 'CREATEFILE', 'RESULT'], proc.stdout.decode(errors='replace'))
            if fields[0] == 'CREATEFILE':
                parts = []
                for count in fields[1:4]:
                    parts.append(stream.read(int(count)))
                    self.assertEqual(stream.read(1), b'\n')
                self.saves.append((parts[0].decode(), parts[1].decode(), parts[2]))
                continue
            value = json.loads(stream.read(int(fields[1])))
            self.assertEqual(stream.read(1), b'\n')
            if fields[0] == 'FETCH':
                self.requests.append(value)
            else:
                self.result = value
        self.assertEqual(self.requests, [])
        self.assertEqual((self.result or {}).get('actions', []), [])
        return proc

    def assertNoWrite(self, proc, code=0):
        self.assertEqual(proc.returncode, code, proc.stderr.decode())
        self.assertEqual(self.saves, [])

    def assertSecretFree(self, proc, *secrets):
        visible = proc.stderr + json.dumps(self.result).encode()
        if not self.saves:
            visible += proc.stdout
        for secret in secrets:
            self.assertNotIn(secret.encode(), visible)

    def test_valid_context_is_written_as_exact_json(self):
        proc = self.execute()
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertEqual(self.saves, [('icloud', 'SplatNet3/auth.json', exported(
            bulletToken=TOKEN, webViewVersion=VERSION, language='ja-JP', userAgent=UA))])
        self.assertEqual(self.saves[0][2].decode(), '{\n  "bulletToken": "%s",\n  "webViewVersion": "%s",\n'
                         '  "language": "ja-JP",\n  "userAgent": "%s"\n}\n' % (TOKEN, VERSION, UA))
        self.assertSecretFree(proc, TOKEN)

    def test_valid_values_are_preserved_and_unknown_versions_accepted(self):
        token, version, ua = ' tok en/+= ', '12345.0.0-ffffffff', 'あ UA\u00a0é'
        proc = self.execute(body={'bulletToken': token, 'lang': 'zz-ZZ'},
                            headers={'x-web-view-ver': version, 'user-agent': ua})
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertEqual(json.loads(self.saves[0][2]), {
            'bulletToken': token, 'webViewVersion': version, 'language': 'zz-ZZ', 'userAgent': ua})

    def test_user_agent_is_omitted_unless_valid(self):
        for ua in (None, '', '  ', 'a\tb', 'a\nb', 'a\x7fb', 'a\x00b'):
            with self.subTest(ua=ua):
                headers = {'x-web-view-ver': VERSION, 'accept-language': 'en-US'}
                if ua is not None:
                    headers['user-agent'] = ua
                proc = self.execute(headers=headers)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode())
                self.assertEqual(self.saves, [('icloud', 'SplatNet3/auth.json', exported(
                    bulletToken=TOKEN, webViewVersion=VERSION, language='ja-JP'))])

    def test_invalid_body_language_falls_back_to_request_language(self):
        absent = {'bulletToken': TOKEN}
        for body in (absent, {**absent, 'lang': ''}, {**absent, 'lang': ' \t'}, {**absent, 'lang': 'ja\nJP'},
                     {**absent, 'lang': 'ja\x7f'}, {**absent, 'lang': 5}, {**absent, 'lang': None},
                     {**absent, 'lang': ['ja-JP']}, {**absent, 'lang': {'a': 1}}, {**absent, 'lang': True}):
            with self.subTest(body=body):
                proc = self.execute(body=body)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode())
                self.assertEqual(json.loads(self.saves[0][2])['language'], 'en-US')

    def test_missing_or_invalid_language_everywhere_fails_generically(self):
        for lang in (None, '', ' ', 'e\nn', 'e\x00n'):
            with self.subTest(lang=lang):
                headers = {'x-web-view-ver': VERSION, 'user-agent': UA}
                if lang is not None:
                    headers['accept-language'] = lang
                proc = self.execute(body={'bulletToken': TOKEN, 'lang': lang}, headers=headers)
                self.assertNoWrite(proc, 6)
                self.assertIsNone(self.result)
                self.assertSecretFree(proc, TOKEN, UA)

    def test_missing_or_invalid_web_version_fails_generically(self):
        for version in (None, '', '  ', '4.0\t', '4\n0', '4\x7f', '4\x00'):
            with self.subTest(version=version):
                headers = {'accept-language': 'en-US', 'user-agent': UA}
                if version is not None:
                    headers['x-web-view-ver'] = version
                proc = self.execute(headers=headers)
                self.assertNoWrite(proc, 6)
                self.assertIsNone(self.result)
                self.assertSecretFree(proc, TOKEN, UA)

    def test_native_rejects_non_string_request_headers_before_the_hook(self):
        for name in ('x-web-view-ver', 'accept-language', 'user-agent'):
            with self.subTest(header=name):
                headers = {'x-web-view-ver': VERSION, 'accept-language': 'en-US', 'user-agent': UA}
                headers[name] = 7
                proc = self.execute(headers=headers)
                self.assertNoWrite(proc, 4)  # QJS_INVALID_INPUT, before Plugin execution.
                self.assertIsNone(self.result)
                self.assertSecretFree(proc, TOKEN, UA)

    def test_invalid_token_is_ignored_without_writing(self):
        for token in (None, '', ' ', '\t \n', 'a\nb', 'a\rb', 'a\x00b', 'a\x1fb', 'a\x7fb', 5, True, ['t'], {'t': 1}):
            with self.subTest(token=token):
                proc = self.execute(body={'bulletToken': token, 'lang': 'ja-JP'})
                self.assertNoWrite(proc)
                self.assertSecretFree(proc, TOKEN, UA)
        for body in ({}, {'lang': 'ja-JP'}, None, [], 'text', 7):
            with self.subTest(body=body):
                self.assertNoWrite(self.execute(body=body))

    def test_non_201_responses_do_not_write(self):
        for status in (200, 202, 204, 302, 400, 401, 403, 429, 500):
            with self.subTest(status=status):
                self.assertNoWrite(self.execute(status=status))

    def test_second_issuance_replaces_the_same_fixed_path(self):
        self.execute()
        first = self.saves
        self.execute(body={'bulletToken': 'synthetic-bullet-token-B', 'lang': 'en-GB'})
        self.assertEqual([item[:2] for item in first + self.saves], [('icloud', 'SplatNet3/auth.json')] * 2)
        self.assertEqual(json.loads(self.saves[0][2])['bulletToken'], 'synthetic-bullet-token-B')
        self.assertNotEqual(first[0][2], self.saves[0][2])

    def test_host_write_failure_stops_without_leaking_credentials(self):
        proc = self.execute(create=b'CREATE_ERROR\n')
        self.assertEqual(len(self.saves), 1)
        self.assertEqual(proc.returncode, 6, proc.stderr.decode())
        self.assertIsNone(self.result)
        self.assertNotIn(TOKEN.encode(), proc.stderr)

    def test_missing_host_reply_does_not_succeed(self):
        proc = self.execute(create=b'')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIsNone(self.result)

    def test_package_matches_generated_manifest_script_and_plugin_source(self):
        self.assertTrue(PACKAGE.is_file(), f'missing built package {PACKAGE.relative_to(ROOT)}')
        package = json.loads(PACKAGE.read_text())
        manifest = json.loads((ROOT / 'build/manifests' / f'{NAME}.json').read_text())
        script = (ROOT / 'build/scripts' / NAME / HOOK).read_text()
        self.assertEqual(package['manifest'], manifest)
        self.assertEqual(package['sourceFiles'], {HOOK: script})
        source = json.loads((ROOT / 'plugins' / NAME / 'plugin.json').read_text())
        self.assertEqual(manifest, {**manifest, **source})
        self.assertEqual({k: source[k] for k in ('schemaVersion', 'version', 'read', 'write', 'endpointBindings', 'settings')}, {
            'schemaVersion': 2, 'version': '1.0.0',
            'read': {'metadata': ['status'], 'headers': ['x-web-view-ver', 'accept-language', 'user-agent'],
                     'queryKeys': [], 'body': {'mode': 'json'}},
            'write': {'requestBody': False, 'responseBody': False, 'files': True},
            'endpointBindings': [], 'settings': {}})
        self.assertRegex(source['id'], r'^[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}$')
        self.assertRegex(source['publishedAt'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        other = [json.loads(p.read_text())['id'] for p in (ROOT / 'plugins').glob('*/plugin.json') if p.parent.name != NAME]
        self.assertNotIn(source['id'], other)
        self.assertNotIn('fetch', script)
        self.assertNotIn('actions', script)


if __name__ == '__main__':
    unittest.main()
