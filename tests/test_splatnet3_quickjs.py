"""Run the generated Plugin through the same C QuickJS bridge used by Interceptor.

Only HTTP responses are fixtures. The Plugin source, Promise handling, JSON
parsing, grant filtering and fetch request validation use the real bridge.
"""
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import test_splatnet3_hook as fx

ROOT = Path(__file__).resolve().parent.parent
SIMULATOR = Path(os.environ.get('INTERCEPTOR_SIMULATOR', str(ROOT / '.tools/bin/interceptor-simulator')))


class SalmonQuickJSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SIMULATOR.is_file():
            raise RuntimeError('Run tools/build-runtime.sh before the shared QuickJS tests')
        build = subprocess.run(['bun', 'run', 'build'], cwd=ROOT, capture_output=True, text=True, timeout=30)
        assert build.returncode == 0, build.stdout + build.stderr
        (ROOT / 'build/evidence').mkdir(parents=True, exist_ok=True)

    def execute(self, replies, *, save_fail_at=None, token='synthetic-token', max_results=50):
        event = {'phase': 'response.onLeave', 'request': {
            'method': 'POST', 'host': 'api.lp1.av5ja.srv.nintendo.net', 'path': '/api/bullet_tokens',
            'headers': {'x-web-view-ver': fx.VERSION, 'accept-language': 'ja-JP'}},
            'response': {'status': 201, 'headers': {}, 'body': {'bulletToken': token, 'lang': 'ja-JP'}}}
        packets = b''
        planned_saves = 0
        if isinstance(replies, bytes):
            packets = replies
        else:
            for status, body in replies:
                raw = body.encode() if isinstance(body, str) else json.dumps(body, separators=(',', ':')).encode()
                packets += f'RESPONSE {status} {len(raw)}\n'.encode() + raw + b'\n'
                # Each test provides a valid history/detail where it expects a publication.
                # The native bridge still checks permissions, JSON and invocation budgets.
                if status == 200:
                    planned_saves += 1
                    packets += b'CREATE_ERROR\n' if planned_saves == save_fail_at else b'CREATED\n'
        with tempfile.TemporaryDirectory(prefix='splatnet3-quickjs-') as directory:
            event_path, config_path = Path(directory) / 'event.json', Path(directory) / 'config.json'
            event_path.write_text(json.dumps(event))
            config_path.write_text(json.dumps({'endpoints': {}, 'settings': {'maxResults': max_results}}))
            proc = subprocess.run([str(SIMULATOR), 'run-package-fetch',
                                   str(ROOT / 'build/dev/plugins/splatnet3-salmon.json'), 'response.onLeave',
                                   str(event_path), str(config_path)], input=packets, capture_output=True, timeout=20)
        stream = io.BytesIO(proc.stdout)
        requests, result = [], None
        self.saves = []
        while line := stream.readline():
            fields = line.decode().strip().split()
            self.assertIn(fields[0], ['FETCH', 'CREATEFILE', 'RESULT'], proc.stdout.decode(errors='replace') + proc.stderr.decode())
            if fields[0] == 'CREATEFILE':
                parts = []
                for count in fields[1:4]:
                    parts.append(stream.read(int(count)))
                    self.assertEqual(stream.read(1), b'\n')
                storage, path, contents = parts
                self.assertTrue(0 < int(fields[4]) <= 10000)
                self.saves.append((storage.decode(), path.decode(), contents))
                continue
            count = int(fields[1])
            value = json.loads(stream.read(count))
            self.assertEqual(stream.read(1), b'\n')
            if fields[0] == 'FETCH':
                self.assertTrue(0 < int(fields[2]) <= 5000)
                requests.append(value)
            else:
                result = value
        return proc, requests, result

    def test_generated_plugin_fetches_history_and_details_in_quickjs(self):
        proc, requests, result = self.execute([(200, fx.history(['d1', 'd1', 'd2'])),
                                               (200, fx.detail('d1')), (200, fx.detail('d2'))])
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertEqual(len(requests), 3)
        for request in requests:
            self.assertEqual(request['url'], 'https://api.lp1.av5ja.srv.nintendo.net/api/graphql')
            self.assertEqual(request['method'], 'POST')
            self.assertEqual(request['headers']['authorization'], 'Bearer synthetic-token')
        bodies = [json.loads(request['body']) for request in requests]
        self.assertEqual(bodies[0]['extensions']['persistedQuery']['sha256Hash'], fx.HISTORY)
        self.assertEqual([body['variables']['coopHistoryDetailId'] for body in bodies[1:]], ['d1', 'd2'])
        self.assertTrue(all(body['extensions']['persistedQuery']['sha256Hash'] == fx.DETAIL for body in bodies[1:]))
        self.assertEqual(result['actions'][0]['json']['acquired'], 2)
        self.assertNotIn('synthetic-token', json.dumps(result))

    def test_expired_token_stops_the_quickjs_chain(self):
        proc, requests, result = self.execute([(200, fx.history(['d1', 'd2'])), (401, {})])
        self.assertEqual(proc.returncode, 6, proc.stderr.decode())
        self.assertIn(b'QuickJS status 6', proc.stderr)  # Script error, not the CPU/wall deadline status.
        self.assertEqual(len(requests), 2)
        self.assertIsNone(result)

    def test_malformed_fixture_replies_fail_without_results(self):
        cases = [
            (b'ERROR\n', 'fixture network failure'),
            (b'bad\n', 'invalid fixture reply'),
            (b'RESPONSE nope 0\n', 'invalid fixture status'),
            (b'RESPONSE 199 0\n', 'invalid fixture response bounds'),
            (b'RESPONSE 600 0\n', 'invalid fixture response bounds'),
            (b'RESPONSE 200 -1\n', 'invalid fixture length'),
            (b'RESPONSE 200 1048577\n', 'invalid fixture response bounds'),
            (b'x' * 129 + b'\n', 'oversized fixture header'),
            (b'RESPONSE 200 5\n{}', 'incomplete fixture body'),
            (b'RESPONSE 200 2\n{}!', 'invalid fixture terminator'),
        ]
        for packets, error in cases:
            with self.subTest(error=error, packets=packets[:40]):
                proc, requests, result = self.execute(packets)
                self.assertEqual(proc.returncode, 6, proc.stderr.decode())
                self.assertIn(error.encode(), proc.stderr)
                self.assertEqual(len(requests), 1)
                self.assertIsNone(result)

    def test_invalid_utf8_response_is_rejected_before_exposing_a_body(self):
        # The setter copies bytes; the shared fetch runtime validates UTF-8 before creating Response.
        proc, requests, result = self.execute(b'RESPONSE 200 1\n\xff\n')
        self.assertEqual(proc.returncode, 6, proc.stderr.decode())
        self.assertEqual(proc.stderr, b'QuickJS status 6\n')
        self.assertEqual(len(requests), 1)
        self.assertIsNone(result)

    def test_original_response_texts_reach_the_native_create_file_callback(self):
        history = ' {"data": ' + json.dumps(fx.history(['d1'])['data']) + '} \n'
        detail = ' {"data": ' + json.dumps(fx.detail('d1')['data']) + '} \n'
        proc, _, result = self.execute([(200, history), (200, detail)])
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertEqual([contents.decode() for _, _, contents in self.saves], [history, detail])
        self.assertEqual([(storage, path) for storage, path, _ in self.saves],
                         [('icloud', 'Salmon Run/history.json'), ('icloud', fx.detail_path('d1'))])
        self.assertEqual(result['actions'][0]['json']['acquired'], 1)

    def test_save_failure_stops_later_work_in_the_real_bridge(self):
        proc, requests, result = self.execute([(200, fx.history(['d1', 'd2'])),
                                              (200, fx.detail('d1')), (200, fx.detail('d2'))], save_fail_at=2)
        self.assertEqual(proc.returncode, 6, proc.stderr.decode())
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(self.saves), 2)
        self.assertIsNone(result)

    def test_incremental_detail_batch_exceeds_heap_without_retaining_bodies(self):
        ids = ['d' + str(n) for n in range(20)]
        replies = [(200, fx.history(ids))]
        for id_ in ids:
            body = fx.detail(id_)
            body['data']['coopHistoryDetail']['padding'] = 'x' * (450 * 1024)
            replies.append((200, body))
        proc, requests, result = self.execute(replies)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertEqual(len(requests), 21)
        self.assertEqual(len(self.saves), 21)
        self.assertEqual(result['actions'][0]['json']['acquired'], 20)

    def test_long_non_ascii_id_hash_in_real_quickjs(self):
        id_ = 'あ' * 300
        proc, _, result = self.execute([(200, fx.history([id_])), (200, fx.detail(id_))])
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertEqual([path for _, path, _ in self.saves], ['Salmon Run/history.json', fx.detail_path(id_)])
        self.assertEqual(result['actions'][0]['json']['acquired'], 1)

    def test_long_ids_finish_after_all_raw_files_are_saved(self):
        # Each request is below 8 KiB; listing all IDs would exceed the 32 KiB result cap.
        # Quotes and backslashes also exercise JSON-escaping overhead.
        ids = [str(n) + 'x"\\' * 300 for n in range(50)]
        texts = [json.dumps(body) + '\n' for body in [fx.history(ids)] + [fx.detail(id_) for id_ in ids]]
        self.assertGreater(len(json.dumps(ids).encode()), 32768)
        proc, requests, result = self.execute([(200, text) for text in texts])
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertEqual(len(requests), 51)
        self.assertEqual([path for _, path, _ in self.saves],
                         ['Salmon Run/history.json'] + [fx.detail_path(id_) for id_ in ids])
        self.assertEqual([contents for _, _, contents in self.saves], [text.encode() for text in texts])
        self.assertEqual(result['actions'][0]['json'],
                         {'version': fx.VERSION, 'acquired': 50, 'unavailable': 0, 'remaining': 0})
        self.assertLessEqual(len(json.dumps(result).encode()), 32768)

    def test_unavailable_long_ids_keep_the_diagnostic_result_bounded(self):
        ids = [str(n) + 'x"\\' * 300 for n in range(50)]
        history = json.dumps(fx.history(ids)) + '\n'
        proc, requests, result = self.execute([(200, history)] + [(404, {})] * 50)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertEqual(len(requests), 51)
        self.assertEqual(self.saves, [('icloud', 'Salmon Run/history.json', history.encode())])
        self.assertEqual(result['actions'][0]['json'],
                         {'version': fx.VERSION, 'acquired': 0, 'unavailable': 50, 'remaining': 0})
        self.assertLessEqual(len(json.dumps(result).encode()), 32768)

    def test_native_host_rejects_unsafe_token_headers_without_exposing_values(self):
        for token in ['private\r\ntoken', 'x' * 5000]:
            with self.subTest(length=len(token)):
                proc, requests, result = self.execute([], token=token)
                self.assertEqual(proc.returncode, 6, proc.stderr.decode())
                self.assertEqual(requests, [])
                self.assertEqual(self.saves, [])
                self.assertIsNone(result)
                self.assertNotIn(token.encode(), proc.stderr + proc.stdout)

    def test_large_history_minimal_detail_and_empty_errors_in_real_quickjs(self):
        ids = [f'd{i}' for i in range(300)]
        body = {'data': {'coopHistoryDetail': {'id': ids[0]}}, 'errors': []}
        proc, requests, result = self.execute([(200, {**fx.history(ids), 'errors': []}), (200, body)], max_results=1)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(self.saves), 2)
        self.assertEqual(result['actions'][0]['json']['remaining'], 299)
        self.assertEqual(json.loads(self.saves[1][2]), body)
