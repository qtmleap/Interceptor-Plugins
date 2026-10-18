"""Exercise the real compiler and packager, never a mock transpiler."""
import json
import shutil
from pathlib import Path

from helpers import Case, REPO


class TypeScriptTests(Case):
    def authored_root(self):
        root = self.make_root()
        shutil.rmtree(root / "scripts")
        (root / "src").mkdir()
        for name, hook in (("request-summary", "onRequest"), ("server-error-filter", "onResponse")):
            (root / "src" / f"{name}.ts").write_text(
                '/// <reference path="../types/interceptor.d.ts" />\n'
                f"function helper(value: string): string {{ return value; }}\n"
                f"function {hook}(event: Interceptor.Event, config: Interceptor.Config): Interceptor.Result {{\n"
                "return { actions: [{type: 'webhook', endpointId: config.endpoints.preview!, json: {value: helper('ok')}}] };\n}\n")
        if (REPO / "types").exists():
            shutil.copytree(REPO / "types", root / "types")
        if (REPO / "tools/compile.mjs").exists():
            shutil.copy(REPO / "tools/compile.mjs", root / "tools/compile.mjs")
        if (REPO / "node_modules").exists():
            (root / "node_modules").symlink_to(REPO / "node_modules", target_is_directory=True)
        return root

    def build(self, root, name="out"):
        out = self.tmp / name
        return self.run_tool(root, "build", "--output", out), out

    def test_compiles_independently_and_packages_exact_javascript(self):
        root = self.authored_root()
        result, out = self.build(root)
        self.ok(result)
        for name in ("request-summary", "server-error-filter"):
            emitted = (root / "build" / "scripts" / f"{name}.js").read_text()
            source = json.loads((out / "plugins" / f"{name}.json").read_text())["source"]
            self.assertEqual(source, emitted)
            self.assertNotIn(": string", source)
            self.assertNotIn("export ", source)
        second, out2 = self.build(root, "second")
        self.ok(second)
        self.assertEqual((out / "plugins/request-summary.json").read_bytes(),
                         (out2 / "plugins/request-summary.json").read_bytes())

    def test_compile_failure_cannot_reuse_stale_output(self):
        root = self.authored_root()
        result, _ = self.build(root)
        self.ok(result)
        script = root / "src/request-summary.ts"
        script.write_text(script.read_text() + "\nconst wrong: number = 'bad';")
        result, out = self.build(root, "failed")
        self.fails(result)
        self.assertFalse(out.exists())

    def test_rebuild_ignores_tampered_output_and_removed_plugin(self):
        root = self.authored_root()
        result, _ = self.build(root)
        self.ok(result)
        (root / "build/scripts/request-summary.js").write_text("tampered")
        (root / "src/server-error-filter.ts").unlink()
        (root / "manifests/server-error-filter.json").unlink()
        result, out = self.build(root, "rebuilt")
        self.ok(result)
        self.assertFalse((root / "build/scripts/server-error-filter.js").exists())
        self.assertNotIn("tampered", (out / "plugins/request-summary.json").read_text())

    def test_rejects_unavailable_apis_modules_async_and_invalid_results(self):
        invalid = ["import fs from 'node:fs';", "export function onRequest() {}",
                   "async function onRequest() { return {actions: []}; }",
                   "fetch('https://example.com');", "setTimeout(() => {}, 1);",
                   "new Uint8Array(4);", "Promise.resolve(1);",
                   "function onRequest(e: Interceptor.Event, c: Interceptor.Config): Interceptor.Result { return {actions: [{type: 'webhook', endpointId: 'x', json: undefined}]}; }"]
        for index, source in enumerate(invalid):
            with self.subTest(source=source):
                root = self.authored_root()
                if "function onRequest" not in source:
                    source = (root / "src/request-summary.ts").read_text() + "\n" + source
                (root / "src/request-summary.ts").write_text(source)
                result, out = self.build(root, f"bad-{index}")
                self.fails(result)
                self.assertFalse(out.exists())

    def test_cannot_link_unemitted_sources_or_inject_host_library_types(self):
        for index, directive in enumerate(('/// <reference path="../shared.ts" />',
                                           '/// <reference lib="dom" />')):
            with self.subTest(directive=directive):
                root = self.authored_root()
                (root / "shared.ts").write_text("function sharedValue(): string { return 'omitted'; }")
                expression = 'sharedValue()' if index == 0 else "(fetch('https://example.com'), 'bad')"
                (root / "src/request-summary.ts").write_text(directive + '\n' +
                    "function onRequest(e: Interceptor.Event, c: Interceptor.Config): Interceptor.Result {" +
                    "return {actions: [{type: 'webhook', endpointId: 'x', json: " + expression + "}]}; }")
                result, out = self.build(root, f"reference-{index}")
                self.fails(result)
                self.assertFalse(out.exists())

    def test_configure_and_guard_do_not_require_generated_sources_or_runtime(self):
        root = self.authored_root()
        self.ok(self.run_tool(root, "configure", "--repository", "alice/ts-plugins", "--name", "Typed plugins",
                              "--url", "https://alice.github.io/ts-plugins/repository.json", "--fingerprint", "a" * 64))
        self.ok(self.run_tool(root, "guard", "--repository", "alice/ts-plugins", "--ref", "refs/heads/master"))
        self.assertFalse((root / "build").exists())

    def test_manifest_hooks_must_have_synchronous_valid_result_even_without_annotations(self):
        for index, source in enumerate(("function onRequest() { return {invalid: 1}; }",
                                        "function differentHook() { return {actions: []}; }")):
            with self.subTest(source=source):
                root = self.authored_root()
                (root / "src/request-summary.ts").write_text(source)
                result, out = self.build(root, f"contract-{index}")
                self.fails(result)
                self.assertFalse(out.exists())

    def test_packaging_executes_with_bun_and_no_node_on_path(self):
        import os
        import subprocess
        import sys
        root = self.authored_root()
        binary = self.tmp / 'bun-only-bin'
        binary.mkdir()
        bun = shutil.which('bun')
        self.assertIsNotNone(bun, 'Bun is required for the authoring suite')
        (binary / 'bun').symlink_to(bun)
        result = subprocess.run([sys.executable, str(root / 'tools/build.py'), '--root', str(root),
                                 '--output', str(self.tmp / 'without-node')],
                                env=dict(os.environ, PATH=str(binary)), capture_output=True, text=True, timeout=60)
        self.ok(result)
        source = json.loads((self.tmp / 'without-node/plugins/request-summary.json').read_text())['source']
        self.assertIn('function onRequest', source)
        self.assertNotIn(': Interceptor.Event', source)


    def test_ds_store_does_not_change_emitted_javascript_or_packages(self):
        root = self.authored_root()
        result, baseline = self.build(root, 'clean-metadata')
        self.ok(result)
        sources = {path.name: path.read_bytes() for path in (root / 'build/scripts').iterdir()}
        (root / 'src/.DS_Store').write_bytes(b'Finder metadata\x00\xff')
        result, actual = self.build(root, 'finder-metadata')
        self.ok(result)
        self.assertEqual({path.name: path.read_bytes() for path in (root / 'build/scripts').iterdir()}, sources)
        for name in ('request-summary.json', 'server-error-filter.json'):
            self.assertEqual((actual / 'plugins' / name).read_bytes(), (baseline / 'plugins' / name).read_bytes())
        (root / 'src/notes.txt').write_text('unexpected source directory entry')
        result, output = self.build(root, 'unexpected-file')
        self.fails(result)
        self.assertFalse(output.exists())
