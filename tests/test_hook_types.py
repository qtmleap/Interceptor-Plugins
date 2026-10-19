"""Check author-facing read-only traffic types without invoking the runtime."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HookTypesTests(unittest.TestCase):
    def test_leave_and_response_request_views_reject_writes(self):
        source = '''
Interceptor.attach({hosts: ['example.com']}, {
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


if __name__ == '__main__':
    unittest.main()
