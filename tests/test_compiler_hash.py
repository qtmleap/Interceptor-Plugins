"""Routed hooks may import exactly js-sha256's sha256, bundled into one self-contained script."""
import hashlib
import json
import os
import shutil
import subprocess

from helpers import REPO, Case
import test_compiler_fetch as fixtures

IMPORT = "import { sha256 } from 'js-sha256';\n"
HOOK = IMPORT + """Interceptor.attach({response: {onLeave: async (res, cfg) => {
  const reply = await fetch('https://example.com/' + sha256('abc'));
  void reply.ok;
}}});
"""
PLAIN = "Interceptor.attach({request: {onEnter(req, cfg) {}}});\n"


class CompilerHashTests(Case):
    # Reuse setup helpers without inheriting or re-discovering the fetch test cases.
    routed_root = fixtures.CompilerFetchTests.routed_root
    build = fixtures.CompilerFetchTests.build
    accepts = fixtures.CompilerFetchTests.accepts
    rejects = fixtures.CompilerFetchTests.rejects

    def test_sha256_import_bundles_one_deterministic_script(self):
        first = self.accepts(HOOK, 'first')
        second = self.accepts(HOOK, 'second')
        self.assertEqual(first, second)
        self.assertLessEqual(len(first.encode()), 131072)
        self.assertIn('Permission is hereby granted', first)
        self.assertIn('js-sha256@1.0.0', first)
        for leaked in ('node_modules', 'require(', 'import ', 'sourceMappingURL', 'eval(', 'process', str(self.tmp), str(REPO)):
            self.assertNotIn(leaked, first)
        self.assertIn('await fetch(', first)

    def test_bundled_sha256_matches_hashlib_in_a_runtime(self):
        bun = shutil.which('bun')
        self.assertTrue(bun)
        source = IMPORT + "Interceptor.attach({request: {onEnter(req, cfg) { Interceptor.send('x', {headers: {a: sha256('abc'), b: sha256('\u00e9')}}); }}});\n"
        script = self.accepts(source, 'send')
        harness = ("let sent = {};\nglobalThis.Interceptor = {attach(h) { h.request.onEnter({}, {}); },"
                   " send(binding, options) { sent = options.headers; }};\n")
        run = subprocess.run([bun, '-e', harness + script + "\nconsole.log(JSON.stringify(sent));"],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), {'a': hashlib.sha256(b'abc').hexdigest(),
                                                   'b': hashlib.sha256('\u00e9'.encode()).hexdigest()})

    def test_only_the_exact_named_import_is_accepted(self):
        body = "Interceptor.attach({request: {onEnter(req, cfg) {}}});\n"
        for index, head in enumerate((
            "import sha256 from 'js-sha256';\n",
            "import { sha256 as hash } from 'js-sha256';\n",
            "import * as hash from 'js-sha256';\n",
            "import type { Hash } from 'js-sha256';\n",
            "import { type sha256 } from 'js-sha256';\n",
            "import { sha256, sha224 } from 'js-sha256';\n",
            "import { sha224 } from 'js-sha256';\n",
            "import { sha256 } from 'js-sha256' with { type: 'json' };\n",
            "import 'js-sha256';\n",
            "import { sha256 } from 'js-sha256';\nimport { sha256 as other } from 'js-sha256';\n",
            "import { sha256 } from 'js-sha256/build/sha256.node.cjs';\n",
            "import { sha256 } from 'js-sha256/src/node.mjs';\n",
            "import { sha256 } from './x';\n",
            "import { createHash } from 'node:crypto';\n",
            "import { sha256 } from 'js-sha256';\nimport fs from 'fs';\n",
            "import sha = require('js-sha256');\n",
            IMPORT + "export { sha256 };\n",
            IMPORT + "export const x = 1;\n",
            IMPORT + "export default 1;\n",
            IMPORT + "const lazy = import('js-sha256');\nvoid lazy;\n",
            IMPORT + "const r = require('js-sha256');\nvoid r;\n",
            IMPORT + "type T = import('js-sha256').Hash;\n",
        )):
            with self.subTest(head=head):
                self.rejects(head + body, f'import-{index}')

    def test_import_is_not_available_to_non_routed_or_legacy_sources(self):
        root = self.make_root()
        (root / 'src').mkdir()
        shutil.copy(REPO / 'tools/compile.mjs', root / 'tools')
        (root / 'types').mkdir()
        shutil.copy(REPO / 'types/interceptor.d.ts', root / 'types')
        (root / 'node_modules').symlink_to(REPO / 'node_modules', target_is_directory=True)
        (root / 'src/request-summary.ts').write_text(IMPORT + "function onRequest(event: Interceptor.Event, config: Interceptor.Config): Interceptor.Result { return { actions: [] }; }\n")
        self.fails(self.run_tool(root, 'build', '--output', self.tmp / 'legacy'))

    def test_host_and_phase_validation_still_applies_with_the_import(self):
        for index, source in enumerate((
            IMPORT + "Interceptor.attach({request: {onEnter: async (req, cfg) => { await 1; }}});\n",
            IMPORT + "Interceptor.attach({response: {onEnter(res, cfg) { void fetch('https://example.com'); }}});\n",
            IMPORT + "const alias = Interceptor;\nInterceptor.attach({request: {onEnter(req, cfg) { void alias; }}});\n",
            IMPORT + "Interceptor.attach({request: {onEnter(req, cfg) { const h: number = sha256('a'); void h; }}});\n",
            IMPORT + "Interceptor.attach({request: {onEnter(req, cfg) { void sha256(1 as unknown as boolean); }}});\n",
            IMPORT + "Interceptor.attach({request: {onEnter(req, cfg) { void new Uint8Array(1); }}});\n",
        )):
            with self.subTest(source=source):
                self.rejects(source, f'guard-{index}')

    def test_sha256_is_only_a_direct_string_hash_call(self):
        for index, expression in enumerate(("sha256.arrayBuffer('a')", "sha256.hmac('k', 'a')",
                                             "sha256.create()", "sha256", "sha256([1, 2])",
                                             "sha256(42 as any)", "{sha256}")):
            with self.subTest(expression=expression):
                self.rejects(IMPORT + 'Interceptor.attach({request: {onEnter(req, cfg) { void ('
                             + expression + '); }}});', f'hash-surface-{index}')

    def test_normal_property_names_are_not_node_or_eval_references(self):
        self.accepts(IMPORT + "Interceptor.attach({request: {onEnter(req, cfg) {"
                     " const data = {process: 'p', Buffer: 'b', Function: 'f'};"
                     " const {process: processValue} = data; class Value { Buffer = 'b'; }"
                     " void sha256(data.process + data.Buffer + data.Function + processValue + new Value().Buffer); }}});", 'property-names')

    def test_bundled_hash_fetches_in_the_shared_quickjs_bridge(self):
        result, output = self.build(HOOK, 'quickjs')
        self.ok(result)
        event = self.tmp / 'event.json'
        config = self.tmp / 'config.json'
        event.write_text(json.dumps({'phase': 'response.onLeave', 'request': {
            'method': 'GET', 'host': 'example.com', 'path': '/', 'headers': {}},
            'response': {'status': 200, 'headers': {}, 'body': {}}}))
        config.write_text(json.dumps({'endpoints': {}, 'settings': {}}))
        simulator = os.environ.get('INTERCEPTOR_SIMULATOR', str(REPO / '.tools/bin/interceptor-simulator'))
        run = subprocess.run([simulator, 'run-package-fetch', str(output / 'plugins/demo.json'),
                              'response.onLeave', str(event), str(config)],
                             input=b'RESPONSE 200 2\n{}\n', capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr.decode())
        lines = run.stdout.splitlines()
        self.assertTrue(lines[0].startswith(b'FETCH '))
        self.assertEqual(json.loads(lines[1])['url'], 'https://example.com/' + hashlib.sha256(b'abc').hexdigest())
        self.assertIn(b'RESULT ', run.stdout)

    def test_postguard_rejects_dynamic_function_construction(self):
        result, _ = self.build(IMPORT + "Interceptor.attach({request: {onEnter(req, cfg) {"
                               " void Function('return 1')(); }}});", 'dynamic-function')
        self.fails(result)
        self.assertIn('Bundled hook contains', result.stderr)

    def test_tampered_dependency_is_rejected(self):
        root = self.routed_root()
        (root / 'plugins/demo/hooks/example.com').mkdir()
        (root / 'plugins/demo/hooks/example.com/GET.ts').write_text(HOOK)
        (root / 'node_modules').unlink()
        package = root / 'node_modules/js-sha256'
        shutil.copytree(REPO / 'node_modules/js-sha256', package)
        (root / 'node_modules/typescript').symlink_to(REPO / 'node_modules/typescript', target_is_directory=True)
        self.ok(self.run_tool(root, 'build', '--output', self.tmp / 'pristine'))
        source = package / 'build/sha256.cjs'
        source.write_text(source.read_text() + '\n// Harmless integrity probe.\n')
        output = self.tmp / 'tampered'
        result = self.run_tool(root, 'build', '--output', output)
        self.fails(result)
        self.assertIn('does not match the pinned 1.0.0 release', result.stderr)
        self.assertFalse(output.exists())

    def test_hooks_without_imports_keep_the_baseline_bytes(self):
        baseline = json.loads((REPO / 'tests/fixtures/compiled-no-import.json').read_text())
        self.assertTrue(baseline)
        for index, (name, fixture) in enumerate(baseline.items()):
            with self.subTest(name=name):
                emitted = self.accepts(fixture['source'], f'baseline-{index}')
                self.assertEqual(hashlib.sha256(emitted.encode()).hexdigest(), fixture['sha256'])
        self.assertEqual(self.accepts(PLAIN, 'plain-a'), self.accepts(PLAIN, 'plain-b'))
