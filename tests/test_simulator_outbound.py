"""Run outbound conformance through the shared C bridge; this CLI never delivers requests."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get('INTERCEPTOR_SIMULATOR', ROOT / '.tools/bin/interceptor-simulator'))
SOURCE_FILE = 'hooks/api.example.com/credentials/POST.js'
PREVIEW_ID = '5E1D0C4A-0000-4000-8000-00000000A001'
BASE = {
    'schemaVersion': 2, 'id': '3F0C9B64-5E0D-4B7A-9C1E-6A7D2B8E4F10', 'name': 'Outbound', 'version': '2.0.0',
    'matches': [{'hosts': ['api.example.com'], 'methods': ['POST'], 'path': {'kind': 'exact', 'value': '/credentials'},
                 'hooks': {'request': {'onEnter': SOURCE_FILE}}}],
    'read': {'metadata': ['method', 'host', 'path', 'status'], 'headers': [], 'queryKeys': [], 'body': {'mode': 'json'}},
    'write': {'requestBody': False, 'responseBody': False}, 'endpointBindings': ['preview'], 'settings': {},
    'outbound': {'lookup': {'url': 'https://api.example.com/profile', 'method': 'GET', 'headers': ['authorization', 'cookie', 'accept']}},
}
EVENT = {
    'phase': 'request.onEnter',
    'request': {'method': 'POST', 'host': 'api.example.com', 'path': '/credentials', 'body': {'ok': True}},
    'response': {'status': 200, 'body': {'accessToken': 'interceptor-test-token'}},
}


class SimulatorOutboundTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(BINARY.is_file(), 'build the Rust simulator against the reviewed outbound C bridge')
        self.temporary = tempfile.TemporaryDirectory(prefix='sim-outbound-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def run_package(self, body='', manifest=None, phase='request.onEnter', source=None):
        metadata = copy.deepcopy(BASE if manifest is None else manifest)
        leg, callback = phase.split('.')
        metadata['matches'][0]['hooks'] = {leg: {callback: SOURCE_FILE}}
        package = {'manifest': metadata, 'sourceFiles': {SOURCE_FILE: source or 'Interceptor.attach({' + leg + ':{' + callback + '(){' + body + '}}});'}}
        event = dict(EVENT, phase=phase)
        paths = []
        for name, value in (('package', package), ('event', event), ('config', {'endpoints': {'preview': PREVIEW_ID}})):
            path = self.directory / (name + '.json')
            path.write_text(json.dumps(value))
            paths.append(str(path))
        return subprocess.run([str(BINARY), 'run-package', paths[0], phase, *paths[1:]], capture_output=True, timeout=10)

    def assert_rejected(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, b'')

    def test_shared_native_and_sdk_declaration_cases(self):
        cases = json.loads((ROOT / 'fixtures/outbound-conformance.json').read_text())['cases']
        for case in cases:
            with self.subTest(case=case['name']):
                result = self.run_package(manifest=dict(BASE, outbound=case['outbound']))
                if case['valid']:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), {'actions': []})
                else:
                    self.assert_rejected(result)

    def test_all_four_callbacks_collect_get_intents_for_original_post(self):
        for phase in ('request.onEnter', 'request.onLeave', 'response.onEnter', 'response.onLeave'):
            with self.subTest(phase=phase):
                result = self.run_package("Interceptor.send('lookup',{headers:{authorization:'Bearer interceptor-test-token'}});", phase=phase)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {'actions': [
                    {'type': 'http', 'binding': 'lookup', 'headers': {'authorization': 'Bearer interceptor-test-token'}},
                ]})

    def test_send_requires_two_arguments_and_required_plain_string_headers(self):
        calls = (
            "Interceptor.send('lookup');", "Interceptor.send('lookup',{});",
            "Interceptor.send('lookup',{headers:{}},{});",
            "Interceptor.send('missing',{headers:{}});",
            "Interceptor.send('lookup',{headers:[]});",
            "Interceptor.send('lookup',{headers:{other:'x'}});",
            "Interceptor.send('lookup',{headers:{authorization:1}});",
            "Interceptor.send('lookup',{headers:{authorization:'x\\r\\ny'}});",
            "Interceptor.send('lookup',{headers:{authorization:'é'}});",
            "Interceptor.send('lookup',{headers:{},url:'https://other.example.com/'});",
        )
        for call in calls:
            with self.subTest(call=call):
                self.assert_rejected(self.run_package('try {' + call + '} catch (error) {}'))
        accepted = self.run_package("Interceptor.send('lookup',{headers:{}});")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout), {'actions': [{'type': 'http', 'binding': 'lookup', 'headers': {}}]})

    def test_registration_calls_and_caught_later_errors_discard_all_intents(self):
        self.assert_rejected(self.run_package(source="try { Interceptor.send('lookup',{headers:{}}); } catch (error) {} Interceptor.attach({request:{onEnter(){}}});"))
        self.assert_rejected(self.run_package("Interceptor.send('lookup',{headers:{}}); try { Interceptor.send('missing',{headers:{}}); } catch (error) {}"))
        self.assert_rejected(self.run_package("Interceptor.send('lookup',{headers:{}}); throw new Error('later');"))

    def test_header_limits_and_combined_action_limit(self):
        accepted = self.run_package("Interceptor.send('lookup',{headers:{authorization:'a'.repeat(4096),cookie:'b'.repeat(4096)}});")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(len(json.loads(accepted.stdout)['actions'][0]['headers']['cookie']), 4096)
        for body in (
            "Interceptor.send('lookup',{headers:{authorization:'a'.repeat(4097)}});",
            "Interceptor.send('lookup',{headers:{authorization:'a'.repeat(4096),cookie:'b'.repeat(4096),accept:'c'}});",
            "Interceptor.send('lookup',{headers:{}}); Interceptor.send('lookup',{headers:{}}); Interceptor.send('lookup',{headers:{}});",
            "Interceptor.send('lookup',{headers:{}}); return {actions:[{type:'webhook',endpointId:'" + PREVIEW_ID + "',json:{}},{type:'webhook',endpointId:'" + PREVIEW_ID + "',json:{}}]};",
        ):
            with self.subTest(body=body):
                self.assert_rejected(self.run_package(body))

        mixed = self.run_package("Interceptor.send('lookup',{headers:{}}); return {actions:[{type:'webhook',endpointId:'" + PREVIEW_ID + "',json:{}}]};")
        self.assertEqual(mixed.returncode, 0, mixed.stderr)
        self.assertEqual(len(json.loads(mixed.stdout)['actions']), 2)

    def test_old_packages_do_not_gain_outbound_access(self):
        manifest = copy.deepcopy(BASE)
        del manifest['outbound']
        unchanged = self.run_package(manifest=manifest)
        self.assertEqual(unchanged.returncode, 0, unchanged.stderr)
        self.assertEqual(json.loads(unchanged.stdout), {'actions': []})
        self.assert_rejected(self.run_package("Interceptor.send('lookup',{headers:{}});", manifest=manifest))
        source = self.directory / 'legacy.js'
        source.write_text("function onRequest(){ Interceptor.send('lookup',{headers:{}}); return {actions:[]}; }")
        event, config = self.directory / 'legacy-event.json', self.directory / 'legacy-config.json'
        event.write_text('{}'); config.write_text('{}')
        result = subprocess.run([str(BINARY), 'run', str(source), 'onRequest', str(event), str(config)], capture_output=True, timeout=10)
        self.assert_rejected(result)

    def test_two_collected_intents_are_reported_in_order(self):
        result = self.run_package("Interceptor.send('lookup',{headers:{authorization:'first'}}); Interceptor.send('lookup',{headers:{cookie:'second'}});")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'actions': [
            {'type': 'http', 'binding': 'lookup', 'headers': {'authorization': 'first'}},
            {'type': 'http', 'binding': 'lookup', 'headers': {'cookie': 'second'}},
        ]})

    # --- POST/PUT JSON bodies -------------------------------------------------------------------

    def methods_manifest(self, post_headers=('content-type', 'authorization')):
        manifest = copy.deepcopy(BASE)
        manifest['outbound'] = {
            'lookup': {'url': 'https://api.example.com/profile', 'method': 'GET', 'headers': ['authorization', 'content-type']},
            'create': {'url': 'https://api.example.com/items', 'method': 'POST', 'headers': list(post_headers)},
            'update': {'url': 'https://api.example.com/items/1', 'method': 'PUT', 'headers': list(post_headers)},
        }
        return manifest

    def send(self, binding, options, prelude='', phase='request.onEnter', manifest=None):
        return self.run_package(prelude + "Interceptor.send('" + binding + "'," + options + ");",
                                manifest=manifest or self.methods_manifest(), phase=phase)

    def assert_actions(self, result, actions):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'actions': actions})

    def test_post_and_put_collect_exact_compact_json_string(self):
        for binding in ('create', 'update'):
            with self.subTest(binding=binding):
                result = self.send(binding, "{headers:{authorization:'x'},json:{a:1,b:[true,null,'s'],c:{}}}")
                self.assert_actions(result, [{'type': 'http', 'binding': binding, 'headers': {'authorization': 'x'},
                                              'jsonBody': '{"a":1,"b":[true,null,"s"],"c":{}}'}])
                # jsonBody is a JSON string, not a nested value
                self.assertIsInstance(json.loads(result.stdout)['actions'][0]['jsonBody'], str)

    def test_json_primitives_and_null(self):
        for literal, expected in (('null', 'null'), ('0', '0'), ('true', 'true'), ("'x'", '"x"'), ('[]', '[]'), ('{}', '{}')):
            with self.subTest(literal=literal):
                self.assert_actions(self.send('create', '{headers:{},json:' + literal + '}'),
                                    [{'type': 'http', 'binding': 'create', 'headers': {}, 'jsonBody': expected}])

    def test_absent_json_on_post_put_has_no_jsonbody_key(self):
        for binding in ('create', 'update'):
            with self.subTest(binding=binding):
                self.assert_actions(self.send(binding, '{headers:{authorization:"x"}}'),
                                    [{'type': 'http', 'binding': binding, 'headers': {'authorization': 'x'}}])

    def test_get_collects_unchanged_shape_and_rejects_any_json_presence(self):
        self.assert_actions(self.send('lookup', '{headers:{authorization:"x"}}'),
                            [{'type': 'http', 'binding': 'lookup', 'headers': {'authorization': 'x'}}])
        for value in ('{}', 'null', 'undefined', '0', '[]'):
            with self.subTest(json=value):
                self.assert_rejected(self.run_package(
                    "try { Interceptor.send('lookup',{headers:{},json:" + value + "}); } catch (error) {}",
                    manifest=self.methods_manifest()))

    def test_present_undefined_json_on_post_put_fails_sticky(self):
        for binding in ('create', 'update'):
            with self.subTest(binding=binding):
                self.assert_rejected(self.run_package(
                    "try { Interceptor.send('" + binding + "',{headers:{},json:undefined}); } catch (error) {}",
                    manifest=self.methods_manifest()))

    def test_snapshot_is_taken_at_send_time(self):
        result = self.run_package(
            "const body={a:1,list:[1]}; Interceptor.send('create',{headers:{},json:body}); body.a=2; body.list.push(2); body.z=true;",
            manifest=self.methods_manifest())
        self.assert_actions(result, [{'type': 'http', 'binding': 'create', 'headers': {}, 'jsonBody': '{"a":1,"list":[1]}'}])

    def test_non_ascii_and_escapes_are_valid_json_strings(self):
        value = "'é日本\\n\"\\\\'"
        result = self.send('create', '{headers:{},json:{k:' + value + '}}')
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(result.stdout)['actions'][0]['jsonBody']
        self.assertEqual(json.loads(body), {'k': 'é日本\n"\\'})
        self.assertNotIn('\n', body)

    def test_body_cap_is_8192_utf8_bytes(self):
        exact = self.send('create', "{headers:{},json:'x'.repeat(8190)}")
        self.assertEqual(exact.returncode, 0, exact.stderr)
        body = json.loads(exact.stdout)['actions'][0]['jsonBody']
        self.assertEqual(len(body.encode()), 8192)
        self.assert_rejected(self.send('create', "{headers:{},json:'x'.repeat(8191)}"))
        # The shared serializer emits raw UTF-8: 2730 three-byte characters plus quotes is exactly 8192 bytes.
        exact_unicode = self.send('update', "{headers:{},json:'日'.repeat(2730)}")
        self.assertEqual(exact_unicode.returncode, 0, exact_unicode.stderr)
        self.assertEqual(len(json.loads(exact_unicode.stdout)['actions'][0]['jsonBody'].encode()), 8192)
        self.assert_rejected(self.send('update', "{headers:{},json:'日'.repeat(2731)}"))

    def test_body_depth_cap_is_16(self):
        def nested(depth):
            return '[' * depth + ']' * depth
        ok = self.send('create', '{headers:{},json:JSON.parse("' + nested(16) + '")}')
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)['actions'][0]['jsonBody'], nested(16))
        self.assert_rejected(self.send('create', '{headers:{},json:JSON.parse("' + nested(17) + '")}'))

    def test_unserializable_json_values_are_rejected_and_discard_intents(self):
        bad = (
            "{get a(){return 1}}", "Object.defineProperty({},'a',{enumerable:true,get(){return 1}})",
            "(()=>{const o={};o.self=o;return o})()", "(()=>{const a=[];a.push(a);return a})()",
            "NaN", "Infinity", "-Infinity", "()=>{}", "Symbol('s')", "10n", "new Date(0)", "new Map()",
            "{a:undefined}", "[undefined]", "{a:()=>1}",
        )
        for value in bad:
            with self.subTest(value=value):
                self.assert_rejected(self.run_package(
                    "Interceptor.send('lookup',{headers:{}}); try { Interceptor.send('create',{headers:{},json:" + value + "}); } catch (error) {}",
                    manifest=self.methods_manifest()))

    def test_user_tojson_is_never_invoked(self):
        result = self.run_package(
            manifest=self.methods_manifest(), source="JSON.stringify=()=>{throw new Error('called')}; "
            "Object.prototype.toJSON=function(){throw new Error('called')}; "
            "Interceptor.attach({request:{onEnter(){Interceptor.send('create',{headers:{},json:{a:1}});}}});")
        self.assert_actions(result, [{'type': 'http', 'binding': 'create', 'headers': {}, 'jsonBody': '{"a":1}'}])

    def test_escaped_bodies_share_the_combined_result_byte_cap(self):
        send = "Interceptor.send('create',{headers:{},json:'\\\\'.repeat(4095)});"
        single = self.run_package(send, manifest=self.methods_manifest())
        self.assertEqual(single.returncode, 0, single.stderr)
        self.assertEqual(len(json.loads(single.stdout)['actions'][0]['jsonBody'].encode()), 8192)
        self.assert_rejected(self.run_package(send + send, manifest=self.methods_manifest()))

    def test_content_type_with_json_must_be_exactly_application_json(self):
        manifest = self.methods_manifest()
        for binding in ('create', 'update'):
            self.assert_actions(self.send(binding, "{headers:{'content-type':'application/json'},json:{}}", manifest=manifest),
                                [{'type': 'http', 'binding': binding, 'headers': {'content-type': 'application/json'}, 'jsonBody': '{}'}])
        for content_type in ('text/plain', 'application/json; charset=utf-8', 'Application/JSON', 'application/jsonx', 'application/x-www-form-urlencoded', ''):
            with self.subTest(content_type=content_type):
                self.assert_rejected(self.send('create', "{headers:{'content-type':'" + content_type + "'},json:{}}", manifest=manifest))

    def test_json_without_content_type_header_is_accepted_for_host_framing(self):
        self.assert_actions(self.send('create', "{headers:{authorization:'x'},json:{}}"),
                            [{'type': 'http', 'binding': 'create', 'headers': {'authorization': 'x'}, 'jsonBody': '{}'}])
        # the binding need not grant content-type: the host emits it
        manifest = self.methods_manifest(post_headers=('authorization',))
        self.assert_actions(self.send('create', "{headers:{},json:{}}", manifest=manifest),
                            [{'type': 'http', 'binding': 'create', 'headers': {}, 'jsonBody': '{}'}])
        self.assert_rejected(self.send('create', "{headers:{'content-type':'application/json'},json:{}}", manifest=manifest))

    def test_header_grants_and_names_are_preserved_for_post_put(self):
        self.assert_rejected(self.send('create', "{headers:{cookie:'x'},json:{}}"))
        self.assert_rejected(self.send('update', "{headers:{'content-length':'2'},json:{}}"))
        self.assert_rejected(self.send('create', "{headers:{authorization:'a'.repeat(4097)},json:{}}"))

    def test_unknown_send_options_are_rejected_for_every_method(self):
        for binding in ('lookup', 'create', 'update'):
            for option in ("method:'POST'", "method:'GET'", "url:'https://other.example.com/'", "jsonBody:'{}'",
                           "body:{}", "path:'/x'", "host:'other.example.com'"):
                with self.subTest(binding=binding, option=option):
                    self.assert_rejected(self.run_package(
                        "try { Interceptor.send('" + binding + "',{headers:{}," + option + "}); } catch (error) {}",
                        manifest=self.methods_manifest()))
                    self.assert_rejected(self.run_package(
                        "try { Interceptor.send('" + binding + "',{headers:{},json:{}," + option + "}); } catch (error) {}",
                        manifest=self.methods_manifest()))

    def test_action_count_and_combined_result_caps_still_apply_with_bodies(self):
        manifest = self.methods_manifest()
        self.assert_rejected(self.run_package(
            "Interceptor.send('create',{headers:{},json:{}}); Interceptor.send('update',{headers:{},json:{}}); Interceptor.send('lookup',{headers:{}});",
            manifest=manifest))
        two = self.run_package("Interceptor.send('create',{headers:{},json:{}}); Interceptor.send('update',{headers:{},json:[]});", manifest=manifest)
        self.assert_actions(two, [{'type': 'http', 'binding': 'create', 'headers': {}, 'jsonBody': '{}'},
                                  {'type': 'http', 'binding': 'update', 'headers': {}, 'jsonBody': '[]'}])
        self.assert_rejected(self.run_package(
            "Interceptor.send('create',{headers:{},json:'x'.repeat(8190)}); Interceptor.send('update',{headers:{},json:'y'.repeat(8190)});"
            "Interceptor.send('lookup',{headers:{}});", manifest=manifest))
        self.assert_rejected(self.run_package(
            "Interceptor.send('create',{headers:{},json:{}}); return {actions:[{type:'webhook',endpointId:'" + PREVIEW_ID + "',json:{}},{type:'webhook',endpointId:'" + PREVIEW_ID + "',json:{}}]};",
            manifest=manifest))
        # combined serialized result stays under 32 KiB: four maximal webhook/body actions are impossible, so the largest accepted mix passes
        mixed = self.run_package(
            "Interceptor.send('create',{headers:{},json:'x'.repeat(8190)}); return {actions:[{type:'webhook',endpointId:'" + PREVIEW_ID + "',json:{}}]};",
            manifest=manifest)
        self.assertEqual(mixed.returncode, 0, mixed.stderr)
        self.assertEqual(len(json.loads(mixed.stdout)['actions']), 2)

    def test_returned_raw_http_actions_remain_invalid(self):
        manifest = self.methods_manifest()
        for action in ("{type:'http',binding:'create',headers:{},jsonBody:'{}'}", "{type:'http',binding:'create',headers:{}}",
                       "{type:'http',method:'POST',url:'https://api.example.com/items',headers:{}}"):
            with self.subTest(action=action):
                self.assert_rejected(self.run_package('return {actions:[' + action + ']};', manifest=manifest))

    def test_post_put_declarations_work_in_all_four_callbacks(self):
        for phase in ('request.onEnter', 'request.onLeave', 'response.onEnter', 'response.onLeave'):
            with self.subTest(phase=phase):
                self.assert_actions(self.send('update', '{headers:{},json:{p:1}}', phase=phase),
                                    [{'type': 'http', 'binding': 'update', 'headers': {}, 'jsonBody': '{"p":1}'}])
