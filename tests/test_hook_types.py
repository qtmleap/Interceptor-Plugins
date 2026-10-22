"""Check author-facing read-only traffic types without invoking the runtime."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HookTypesTests(unittest.TestCase):
    def test_leave_and_response_request_views_reject_writes(self):
        source = '''
// @ts-expect-error route conditions and IDs are not part of the JS API
Interceptor.attach('search', {});
// @ts-expect-error host/path/method come from the file location
Interceptor.attach({hosts: ['example.com']}, {});
// @ts-expect-error Match is not an author-facing type
const match: Interceptor.Match = {};
Interceptor.attach({
  request: {
    onEnter(request) { request.body.limit = 5; request.body = {limit: 5}; },
    onLeave(request) {
      // @ts-expect-error leave bodies cannot be replaced
      request.body = {limit: 5};
      if (request.body && typeof request.body === 'object' && 'limit' in request.body) {
        const value: Interceptor.ReadOnlyJSON = request.body.limit;
        void value;
        // @ts-expect-error a narrowed object still rejects in-place writes
        request.body.limit = 5;
      }
    }
  },
  response: {
    onEnter(response) {
      response.body.maintenance = true;
      // @ts-expect-error the corresponding request is read-only even on response enter
      response.request.body = {};
      if (response.request.body && typeof response.request.body === 'object' && 'limit' in response.request.body) {
        const value: Interceptor.ReadOnlyJSON = response.request.body.limit;
        void value;
        // @ts-expect-error the narrowed corresponding request body is read-only
        response.request.body.limit = 5;
      }
    },
    onLeave(response) {
      if (response.body && typeof response.body === 'object' && 'maintenance' in response.body) {
        const value: Interceptor.ReadOnlyJSON = response.body.maintenance;
        void value;
        // @ts-expect-error the narrowed response leave body is read-only
        response.body.maintenance = true;
      }
    }
  }
});
'''
        with tempfile.TemporaryDirectory(prefix='hook-types-') as temporary:
            path = Path(temporary) / 'hooks.ts'
            path.write_text(f'/// <reference path="{ROOT / "types/interceptor.d.ts"}" />\n' + source)
            result = subprocess.run(['bun', str(ROOT / 'node_modules/typescript/bin/tsc'), '--strict',
                                     '--noEmit', '--target', 'ES2020', str(path)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_send_accepts_only_binding_and_string_headers(self):
        source = '''
Interceptor.send('lookup', {headers: {authorization: 'Bearer x'}});
const result: void = Interceptor.send('lookup', {headers: {}});
void result;
// @ts-expect-error options are required
Interceptor.send('lookup');
// @ts-expect-error the headers map is required even when empty
Interceptor.send('lookup', {});
// @ts-expect-error URLs come from the manifest
Interceptor.send('lookup', {headers: {}, url: 'https://example.com/'});
// @ts-expect-error the method is declared in the manifest
Interceptor.send('lookup', {headers: {}, method: 'POST'});
// @ts-expect-error raw bodies are not supported
Interceptor.send('lookup', {headers: {}, body: {}});
// @ts-expect-error header values are plain strings
Interceptor.send('lookup', {headers: {a: 1}});
// @ts-expect-error send has no Promise result
Interceptor.send('lookup', {headers: {}}).then(() => {});
// @ts-expect-error the binding is required
Interceptor.send();
const options: Interceptor.SendOptions = {headers: {accept: 'application/json'}};
void options;
'''
        with tempfile.TemporaryDirectory(prefix='send-types-') as temporary:
            path = Path(temporary) / 'send.ts'
            path.write_text(f'/// <reference path="{ROOT / "types/interceptor.d.ts"}" />\n' + source)
            result = subprocess.run(['bun', str(ROOT / 'node_modules/typescript/bin/tsc'), '--strict',
                                     '--noEmit', '--target', 'ES2020', str(path)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_send_json_option_is_typed_and_registered_callbacks_accept_it(self):
        source = '''
Interceptor.attach({
  request: {
    onLeave(request) {
      if (request.body !== undefined) Interceptor.send('create', {headers: {}, json: request.body});
    }
  },
  response: {
    onLeave(response) {
      if (response.body !== undefined) Interceptor.send('create', {headers: {}, json: response.body});
      Interceptor.send('create', {headers: {'content-type': 'application/json'}, json: {a: 1, list: [true, null, 'x']}});
      Interceptor.send('create', {headers: {}, json: null});
      Interceptor.send('update', {headers: {}, json: 'text'});
      Interceptor.send('update', {headers: {}});
    }
  }
});
// legacy GET shape is unchanged
Interceptor.send('lookup', {headers: {authorization: 'Bearer x'}});
const options: Interceptor.SendOptions = {headers: {}, json: {nested: {value: 1}}};
void options;
const tuple = [1, 'x', null] as const;
Interceptor.send('create', {headers: {}, json: tuple});
const nested: {readonly values: readonly (readonly number[])[]} = {values: [[1, 2]]};
Interceptor.send('create', {headers: {}, json: nested});
const result: void = Interceptor.send('create', {headers: {}, json: []});
void result;
// @ts-expect-error jsonBody is internal to the host action, not a script option
Interceptor.send('create', {headers: {}, jsonBody: '{}'});
// @ts-expect-error methods are declared in the manifest
Interceptor.send('create', {headers: {}, json: {}, method: 'PUT'});
// @ts-expect-error URLs come from the manifest
Interceptor.send('create', {headers: {}, json: {}, url: 'https://example.com/'});
// @ts-expect-error functions are not JSON
Interceptor.send('create', {headers: {}, json: () => {}});
// @ts-expect-error symbols are not JSON
Interceptor.send('create', {headers: {}, json: Symbol('s')});
// @ts-expect-error the headers map stays required with json
Interceptor.send('create', {json: {}});
// @ts-expect-error raw body option is not supported
Interceptor.send('create', {headers: {}, body: {}});
'''
        with tempfile.TemporaryDirectory(prefix='send-json-types-') as temporary:
            path = Path(temporary) / 'send-json.ts'
            path.write_text(f'/// <reference path="{ROOT / "types/interceptor.d.ts"}" />\n' + source)
            result = subprocess.run(['bun', str(ROOT / 'node_modules/typescript/bin/tsc'), '--strict',
                                     '--noEmit', '--target', 'ES2020', str(path)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
