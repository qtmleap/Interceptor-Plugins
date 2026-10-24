"""Ordinary installed package resolution without a package-specific compiler policy."""
import json
import os
import shutil
import subprocess
import sys

from helpers import Case, REPO
import test_compiler_fetch as fixtures


class BundlingTests(Case):
    def compile(self, imports, expression, packages, name='output', env=None, copy_typescript=False):
        root = fixtures.CompilerFetchTests.routed_root(self)
        (root / 'package.json').write_text((REPO / 'package.json').read_text())
        (root / 'node_modules').unlink()
        (root / 'node_modules').mkdir()
        for child in (REPO / 'node_modules').iterdir():
            if child.name.startswith('@'):
                scope = root / 'node_modules' / child.name
                scope.mkdir()
                for member in child.iterdir():
                    (scope / member.name).symlink_to(member, target_is_directory=True)
            elif child.name == 'typescript' and copy_typescript:
                shutil.copytree(child, root / 'node_modules' / child.name)
            elif not child.name.startswith('.'):
                (root / 'node_modules' / child.name).symlink_to(child, target_is_directory=True)
        for package, files in packages.items():
            folder = root / 'node_modules' / package
            folder.mkdir(parents=True)
            for path, text in files.items():
                destination = folder / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                if path == 'package.json' and isinstance(text, dict):
                    text = {**text, 'name': package}
                destination.write_text(json.dumps(text) if isinstance(text, dict) else text)
        hook = root / 'plugins/demo/hooks/example.com/GET.ts'
        hook.parent.mkdir()
        hook.write_text(imports + '\nInterceptor.attach({response: {async onLeave(res, cfg) {'
                        + "await fetch('https://example.com/', {method: 'POST', body: JSON.stringify(" + expression + ')}); }}});')
        output = self.tmp / name
        result = subprocess.run([sys.executable, str(root / 'tools/build.py'), '--root', str(root), '--output', str(output)],
                                cwd=root, env=env, capture_output=True, text=True)
        return result, output

    def fetch_result(self, output):
        event = self.tmp / 'event.json'
        config = self.tmp / 'config.json'
        event.write_text(json.dumps({'phase': 'response.onLeave', 'request': {
            'method': 'GET', 'host': 'example.com', 'path': '/', 'headers': {}},
            'response': {'status': 200, 'headers': {}, 'body': {}}}))
        config.write_text('{"endpoints":{},"settings":{}}')
        simulator = os.environ.get('INTERCEPTOR_SIMULATOR', str(REPO / '.tools/bin/interceptor-simulator'))
        run = subprocess.run([simulator, 'run-package-fetch', str(output / 'plugins/demo.json'),
                              'response.onLeave', str(event), str(config)],
                             input=b'RESPONSE 200 2\n{}\n', capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr.decode() + repr(run.stdout))
        self.assertIn(b'RESULT ', run.stdout)
        return json.loads(json.loads(run.stdout.splitlines()[1])['body'])

    def package(self, source, declarations='export function value(): string;', **metadata):
        return {'package.json': {'name': 'fixture', 'version': '1.0.0', 'type': 'module',
                                 'main': 'index.js', 'types': 'index.d.ts', **metadata},
                'index.js': source, 'index.d.ts': declarations, 'LICENSE': 'Fixture test license\n'}

    def test_scoped_subpath_namespace_and_transitive_imports(self):
        packages = {'@fixture/main': self.package("export { value } from 'fixture-dep';", exports={'./part': './index.js'}),
                    'fixture-dep': self.package("export { value } from './internal.js';")}
        packages['fixture-dep']['internal.js'] = "export function value(){return 'transitive';}"
        packages['fixture-dep']['internal.d.ts'] = 'export function value(): string;'
        result, output = self.compile("import * as pkg from '@fixture/main/part';", 'pkg.value()', packages)
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'transitive')

    def test_constant_template_literal_require_is_bundled(self):
        for index, gap in enumerate(['', ' /* static dependency */ ']):
            with self.subTest(gap=gap):
                package = self.package('exports.value = require' + gap + '(`./value.js`);', type='commonjs')
                package['value.js'] = "module.exports = function(){return 'static-require';};"
                result, output = self.compile("import {value} from 'fixture-lib';", 'value()',
                                              {'fixture-lib': package}, f'require-{index}')
                self.ok(result)
                self.assertEqual(self.fetch_result(output), 'static-require')

    def test_constant_template_literal_dependency_import_is_bundled(self):
        for index, gap in enumerate(['', ' /* static dependency */ ']):
            with self.subTest(gap=gap):
                package = self.package('export async function value(){return (await import' + gap + '(`./value.js`)).value;}',
                                       'export function value(): Promise<string>;')
                package['value.js'] = "export const value='static-import';"
                result, output = self.compile("import {value} from 'fixture-lib';", 'await value()',
                                              {'fixture-lib': package}, f'import-{index}')
                self.ok(result)
                self.assertEqual(self.fetch_result(output), 'static-import')

    def test_json_dependency_loading_words_are_data(self):
        package = self.package("export {default as value} from './value.json';", 'export const value: {text: string};')
        package['value.json'] = '{"text":"require(key); import.meta"}'
        result, output = self.compile("import {value} from 'fixture-lib';", 'value.text', {'fixture-lib': package})
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'require(key); import.meta')

    def test_feature_detection_locals_and_standard_function_work_in_quickjs(self):
        source = "export function value(){ const Buffer = 'local'; return typeof process !== 'undefined' ? process.platform : Buffer + Function('return 7')(); }"
        result, output = self.compile("import {value as run} from 'fixture-lib';", 'run()', {'fixture-lib': self.package(source)})
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'local7')

    def test_feature_detection_rejects_branches_that_execute_when_api_is_absent(self):
        for index, body in enumerate([
            "if (typeof process === 'undefined') return process.platform; return 'safe';",
            "return typeof process === 'undefined' ? process.platform : 'safe';",
            "return typeof process === 'undefined' && process.platform;",
            "return typeof process !== 'undefined' || process.platform;",
            "return (typeof process !== 'undefined' || Math.random() > 0) && process.platform;",
        ]):
            with self.subTest(body=body):
                result, output = self.compile("import {value} from 'fixture-lib';", 'value()',
                    {'fixture-lib': self.package('export function value(){' + body + '}')}, f'unsafe-{index}')
                self.fails(result)
                self.assertIn('unsupported runtime API process', result.stderr)
                self.assertFalse(output.exists())

    def test_feature_detection_accepts_safe_negative_and_compound_branches(self):
        for index, body in enumerate([
            "if (typeof process === 'undefined') return 'safe'; else return process.platform;",
            "return typeof process === 'undefined' ? 'safe' : process.platform;",
            "return typeof process === 'undefined' || process.platform ? 'safe' : 'unexpected';",
            "return typeof process !== 'undefined' && Math.random() > 0 && process.platform || 'safe';",
        ]):
            with self.subTest(body=body):
                result, output = self.compile("import {value} from 'fixture-lib';", 'value()',
                    {'fixture-lib': self.package('export function value(){' + body + '}')}, f'safe-{index}')
                self.ok(result)
                self.assertEqual(self.fetch_result(output), 'safe')

    def test_multi_api_feature_detection_accepts_only_unreachable_branches(self):
        for name, body, allowed in [
            ('safe', "return typeof window !== 'undefined' && typeof document !== 'undefined' && document.title || 'fallback';", True),
            ('unsafe', "return typeof window !== 'undefined' || document.title;", False),
        ]:
            with self.subTest(name=name):
                result, output = self.compile("import {value} from 'fixture-lib';", 'value()',
                    {'fixture-lib': self.package('export function value(){' + body + '}')}, name)
                if allowed:
                    self.ok(result)
                    self.assertEqual(self.fetch_result(output), 'fallback')
                else:
                    self.fails(result)
                    self.assertIn('unsupported runtime API document', result.stderr)
                    self.assertFalse(output.exists())

    def test_type_only_and_transitive_declarations(self):
        packages = {'fixture-lib': self.package('export const unused=1;', "export type { Value } from './shape';"),}
        packages['fixture-lib']['shape.d.ts'] = 'export type Value = string;'
        result, output = self.compile("import type {Value} from 'fixture-lib'; const x: Value = 'typed';", 'x', packages)
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'typed')

    def test_namespace_qualified_types_and_type_queries(self):
        package = self.package("export function value(){return 'typed';}",
            'export type Value = string; export function value(): Value;')
        result, output = self.compile("import * as pkg from 'fixture-lib'; const run: typeof pkg.value = pkg.value; const x: pkg.Value = run();",
                                      'x', {'fixture-lib': package})
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'typed')

    def test_new_target_is_a_supported_javascript_feature(self):
        source = "export function value(){ function Box(){this.text = new.target ? 'constructed' : 'called';} return new Box().text; }"
        result, output = self.compile("import {value} from 'fixture-lib';", 'value()', {'fixture-lib': self.package(source)})
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'constructed')

    def test_umd_wrapper_uses_global_this_without_evaluating_self(self):
        source = """(function(global, factory) {
          typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports) :
          typeof define === 'function' && define.amd ? define(['exports'], factory) :
          (global = typeof globalThis !== 'undefined' ? globalThis : global || self, factory(global.fixture = {}));
        })(this, function(exports) { exports.value = function(){return 'umd';}; });"""
        result, output = self.compile("import {value} from 'fixture-lib';", 'value()',
                                      {'fixture-lib': self.package(source, type='commonjs')})
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'umd')

    def test_installed_packages_can_share_node_builtin_names(self):
        events = self.package("export function value(){return 'wrong';}", exports={'.': {
            'browser': {'import': './browser.js', 'require': './require.cjs'}, 'default': './index.js'}})
        events['browser.js'] = "export function value(){return 'installed-import';}"
        events['browser.d.ts'] = 'export function value(): string;'
        events['require.cjs'] = "exports.value = function(){return 'installed-require';};"
        packages = {'events': events, 'ws': self.package("module.exports = require('events');", type='commonjs')}
        for name, expected in [('events', 'installed-import'), ('ws', 'installed-require')]:
            with self.subTest(name=name):
                result, output = self.compile(f"import {{value}} from '{name}';", 'value()', packages, name)
                self.ok(result)
                self.assertEqual(self.fetch_result(output), expected)

    def test_browser_false_builtin_is_an_empty_module(self):
        package = self.package("const crypto = require('crypto'); exports.value = function(){return typeof crypto.randomBytes === 'function' ? crypto.randomBytes() : 'fallback';};",
                               type='commonjs', browser={'crypto': False})
        result, output = self.compile("import {value} from 'fixture-lib';", 'value()', {'fixture-lib': package})
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'fallback')

    def test_license_order_uses_code_units(self):
        packages = {name: self.package("export function value(){return 'x';}") for name in ['a-pkg', 'Z-pkg']}
        result, output = self.compile("import {value as a} from 'a-pkg'; import {value as z} from 'Z-pkg';", 'a()+z()', packages)
        self.ok(result)
        script = json.loads((output / 'plugins/demo.json').read_text())['sourceFiles']['hooks/example.com/GET.js']
        self.assertLess(script.index('Z-pkg@1.0.0'), script.index('a-pkg@1.0.0'))

    def test_browser_export_condition_matches_types(self):
        package = self.package("export function value(){return 'wrong';}", exports={'.': {
            'browser': {'types': './browser.d.ts', 'default': './browser.js'},
            'default': './index.js'}})
        package['browser.js'] = "export function value(){return 'browser';}"
        package['browser.d.ts'] = 'export function value(): "browser";'
        result, output = self.compile("import {value} from 'fixture-lib'; const x: 'browser'=value();", 'x', {'fixture-lib': package})
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'browser')

    def test_missing_types_and_package_report_build_errors_without_output(self):
        package = self.package('export function value(){return 1;}')
        del package['index.d.ts']
        for name, packages in [('untyped', {'fixture-lib': package}), ('missing', {})]:
            with self.subTest(name=name):
                result, output = self.compile("import {value} from 'fixture-lib';", 'value()', packages, name)
                self.fails(result)
                self.assertIn('fixture-lib', result.stderr)
                self.assertFalse(output.exists())

    def test_dependency_globals_do_not_expand_authored_api(self):
        package = self.package('export function value(){return "x";}', 'declare global { const sneaky: string; } export function value(): string;')
        result, output = self.compile("import {value} from 'fixture-lib';", 'sneaky + value()', {'fixture-lib': package})
        self.fails(result)
        self.assertIn('global', result.stderr)
        self.assertFalse(output.exists())

    def test_standard_library_globals_work_with_a_non_symlinked_typescript_install(self):
        package = self.package("export function value(){return 'ok';}")
        result, output = self.compile("import {value} from 'fixture-lib';", "JSON.stringify(Object.keys({a: value()}))",
                                      {'fixture-lib': package}, copy_typescript=True)
        self.ok(result)
        self.assertEqual(self.fetch_result(output), '["a"]')

    def test_dom_library_globals_remain_unavailable(self):
        package = self.package("export function value(){return 'x';}",
                               '/// <reference lib="dom" />\nexport function value(): string;')
        result, output = self.compile("import {value} from 'fixture-lib';", 'document.title + value()', {'fixture-lib': package})
        self.fails(result)
        self.assertIn('dependency-only global', result.stderr)
        self.assertFalse(output.exists())

    def test_unsupported_runtime_dependencies_fail_without_output(self):
        for name, source, files in [
            ('builtin', "import fs from 'node:fs'; export function value(){return fs.readFileSync('x');}", {}),
            ('runtime', 'export function value(){return process.pid;}', {}),
            ('native', "import addon from './addon.node'; export function value(){return addon;}", {'addon.node': 'binary'}),
            ('dynamic', 'export function value(key){return require(key);}', {}),
            ('commented-dynamic', 'export function value(key){return require /* dependency loader */ (key);}', {}),
            ('escaped-dynamic', r'export function value(key){return requ\u0069re(key);}', {}),
            ('commented-meta', 'export function value(){return import /* dependency metadata */ .meta.url;}', {}),
        ]:
            with self.subTest(name=name):
                package = self.package(source, 'export function value(key?: string): string;')
                package.update(files)
                result, output = self.compile("import {value} from 'fixture-lib';", 'value()', {'fixture-lib': package}, name)
                self.fails(result)
                if name in ('commented-dynamic', 'escaped-dynamic'):
                    self.assertIn('Unsupported runtime module loading', result.stderr)
                elif name == 'commented-meta':
                    self.assertIn('Unsupported import.meta', result.stderr)
                self.assertFalse(output.exists())

    def test_bundle_budget_includes_dependencies(self):
        package = self.package('export const value="' + 'x' * 140000 + '";', 'export const value: string;')
        result, output = self.compile("import {value} from 'fixture-lib';", 'value', {'fixture-lib': package})
        self.fails(result)
        self.assertIn('too large', result.stderr)
        self.assertFalse(output.exists())

    def test_identical_bytes_across_roots_and_node_env_with_license(self):
        scripts = []
        for index, env in enumerate(['development', 'test']):
            package = self.package("export function value(){return process.env.NODE_ENV;}")
            result, output = self.compile("import {value} from 'fixture-lib';", 'value()', {'fixture-lib': package},
                                          f'out-{index}', {**os.environ, 'NODE_ENV': env})
            self.ok(result)
            scripts.append(json.loads((output / 'plugins/demo.json').read_text())['sourceFiles']['hooks/example.com/GET.js'])
        self.assertEqual(*scripts)
        self.assertIn('Fixture test license', scripts[0])
        self.assertNotIn(str(self.tmp), scripts[0])

    def test_subpath_retains_root_license_through_type_only_package_metadata(self):
        package = self.package('', exports={'./part': './esm/index.js'})
        package.update({'esm/package.json': {'type': 'module'},
                        'esm/index.js': "export function value(){return 'subpath';}",
                        'esm/index.d.ts': 'export function value(): string;',
                        'LICENSE': 'Subpath root license marker'})
        result, output = self.compile("import {value} from 'fixture-lib/part';", 'value()', {'fixture-lib': package})
        self.ok(result)
        script = json.loads((output / 'plugins/demo.json').read_text())['sourceFiles']['hooks/example.com/GET.js']
        self.assertIn('Subpath root license marker', script)

    def test_repeated_package_metadata_retains_root_license(self):
        package = self.package('', exports={'./part': './dist/index.js'})
        package.update({'dist/package.json': {'name': 'fixture-lib', 'version': '1.0.0', 'type': 'module'},
                        'dist/index.js': "export function value(){return 'dist';}",
                        'dist/index.d.ts': 'export function value(): string;',
                        'LICENSE': 'Repeated metadata root license marker'})
        result, output = self.compile("import {value} from 'fixture-lib/part';", 'value()', {'fixture-lib': package})
        self.ok(result)
        script = json.loads((output / 'plugins/demo.json').read_text())['sourceFiles']['hooks/example.com/GET.js']
        self.assertIn('Repeated metadata root license marker', script)

    def test_commonjs_with_separately_installed_types(self):
        library = {'package.json': {'name': 'fixture-lib', 'version': '1.0.0', 'main': 'index.js'},
                   'index.js': "module.exports = function(){return 'separate-types';};"}
        types = {'package.json': {'name': '@types/fixture-lib', 'version': '1.0.0', 'types': 'index.d.ts'},
                 'index.d.ts': 'declare function value(): string; export = value;'}
        result, output = self.compile("import value from 'fixture-lib';", 'value()',
                                      {'fixture-lib': library, '@types/fixture-lib': types})
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'separate-types')

    def test_side_effect_import_initializes_the_bundle(self):
        package = self.package("Object.defineProperty(Object.prototype, 'fixtureValue', {value: 'initialized'});")
        result, output = self.compile("import 'fixture-lib';", "({} as {fixtureValue: string}).fixtureValue", {'fixture-lib': package})
        self.ok(result)
        self.assertEqual(self.fetch_result(output), 'initialized')


class EditorConfigurationTests(Case):
    def tsc(self, project):
        return subprocess.run(['bun', str(REPO / 'node_modules/typescript/bin/tsc'),
                               '--noEmit', '--project', str(project)],
                              cwd=REPO, capture_output=True, text=True, timeout=30)

    def test_workspace_project_resolves_the_checked_in_package_imports(self):
        self.ok(self.tsc(REPO / 'tsconfig.json'))

    def test_inherited_editor_options_support_commonjs_and_browser_types(self):
        root = self.tmp / 'editor'
        modules = root / 'node_modules'
        modules.mkdir(parents=True)
        for name in ['js-sha256', 'fast-json-stable-stringify']:
            (modules / name).symlink_to(REPO / 'node_modules' / name, target_is_directory=True)
        browser = modules / 'editor-browser-types'
        browser.mkdir()
        (browser / 'package.json').write_text(json.dumps({'name': 'editor-browser-types', 'version': '1.0.0',
            'exports': {'.': {'browser': './browser.d.ts', 'default': './node.d.ts'}}}))
        (browser / 'browser.d.ts').write_text("export declare const platform: 'browser';")
        (browser / 'node.d.ts').write_text("export declare const platform: 'node';")
        (root / 'editor.ts').write_text("""import {sha256} from 'js-sha256';
import stringify from 'fast-json-stable-stringify';
import {platform} from 'editor-browser-types';
const browserOnly: 'browser' = platform;
const text: string = stringify({hash: sha256(browserOnly)});
Interceptor.attach({response: {onLeave() { stringify(text); }}});
""")
        project = root / 'tsconfig.json'
        project.write_text(json.dumps({'extends': str(REPO / 'tsconfig.json'), 'include': [],
            'files': [str(REPO / 'types/interceptor.d.ts'), 'editor.ts']}))
        self.ok(self.tsc(project))
