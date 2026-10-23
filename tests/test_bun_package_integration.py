"""Bun-installed ESM/CJS packages run from generated hooks on the shared C QuickJS bridge."""
import json
import os
import shutil
import subprocess
from pathlib import Path

from helpers import Case, REPO
import test_compiler_fetch as fixtures


class BunPackageIntegrationTests(Case):
    def routed_root(self):
        root = fixtures.CompilerFetchTests.routed_root(self)
        shutil.copy(REPO / 'package.json', root / 'package.json')
        return root

    build = fixtures.CompilerFetchTests.build

    def assert_fetch_body(self, import_line, expression, expected, name):
        source = import_line + '\nInterceptor.attach({response: {async onLeave(res, cfg) {' \
                 + " await fetch('https://example.com/', {method: 'POST', body: " + expression + '}); }}});'
        result, output = self.build(source, name)
        self.ok(result)
        script = json.loads((output / 'plugins/demo.json').read_text())['sourceFiles']['hooks/example.com/GET.js']
        for leaked in [str(REPO), str(self.tmp), 'node_modules/', '../../']:
            self.assertNotIn(leaked, script)
        event = self.tmp / f'{name}-event.json'
        config = self.tmp / f'{name}-config.json'
        event.write_text(json.dumps({'phase': 'response.onLeave', 'request': {
            'method': 'GET', 'host': 'example.com', 'path': '/', 'headers': {}},
            'response': {'status': 200, 'headers': {}, 'body': {}}}))
        config.write_text(json.dumps({'endpoints': {}, 'settings': {}}))
        simulator = Path(os.environ.get('INTERCEPTOR_SIMULATOR', REPO / '.tools/bin/interceptor-simulator'))
        self.assertTrue(simulator.is_file(), 'Run tools/build-runtime.sh before the shared QuickJS integration tests')
        run = subprocess.run([str(simulator), 'run-package-fetch', str(output / 'plugins/demo.json'),
                              'response.onLeave', str(event), str(config)],
                             input=b'RESPONSE 200 2\n{}\n', capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr.decode())
        lines = run.stdout.splitlines()
        self.assertTrue(lines[0].startswith(b'FETCH '), run.stdout)
        request = json.loads(lines[1])
        self.assertEqual(request['body'], expected)
        self.assertIn(b'RESULT ', run.stdout)

    def test_esm_default_import_runs_on_quickjs(self):
        self.assert_fetch_body("import escape from 'escape-string-regexp';",
                               "JSON.stringify(escape('a.b'))", json.dumps('a\\.b'), 'esm')

    def test_commonjs_default_import_runs_on_quickjs(self):
        self.assert_fetch_body("import stringify from 'fast-json-stable-stringify';",
                               'stringify({b: 2, a: 1})', '{"a":1,"b":2}', 'commonjs')
