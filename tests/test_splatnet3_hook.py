import hashlib
import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path(os.environ.get('SPLATNET3_TEST_SOURCE', str(ROOT / 'build/scripts/splatnet3-salmon/hooks/api.lp1.av5ja.srv.nintendo.net/api/bullet_tokens/POST.js')))


def setUpModule():
    if 'SPLATNET3_TEST_SOURCE' not in os.environ:
        build = subprocess.run(['bun', 'run', 'build'], cwd=ROOT, capture_output=True, text=True, timeout=30)
        if build.returncode != 0:
            raise RuntimeError(build.stdout + build.stderr)


VERSION = '4.0.0-091d4283'
HISTORY = '0f8c33970a425683bb1bdecca50a0ca4fb3c3641c0b2a1237aedfde9c0cb2b8f'
DETAIL = '824a1e22c4ad4eece7ad94a9a0343ecd76784be4f77d8f6f563c165afc8cf602'

VERSION_10 = '10.0.0-d15503c4'
HISTORY_10 = 'e11a8cf2c3de7348495dea5cdcaa25e0c153541c4ed63f044b6c174bc5b703df'
DETAIL_10 = 'f2d55873a9281213ae27edc171e2b19131b3021a2ae263757543cdd3bf015cc8'


def response(**changes):
    value = {'status': 201, 'body': {'bulletToken': 'synthetic-token'},
             'request': {'headers': {'x-web-view-ver': VERSION, 'accept-language': 'ja-JP'}}}
    value.update(changes)
    return value


def history(ids):
    return {'data': {'coopResult': {'historyGroups': {'nodes': [
        {'historyDetails': {'nodes': [{'id': i} for i in ids]}}
    ]}}}}


def detail(id_, player='synthetic-player'):
    return {'data': {'coopHistoryDetail': {'id': id_, 'myResult': {'player': {'id': player}}}}}


def detail_path(id_):
    return 'Salmon Run/details/' + hashlib.sha256(id_.encode()).hexdigest() + '.json'


def run(res=None, replies=None, settings=None, save_fail_at=None):
    payload = {'source': str(SOURCE), 'response': response() if res is None else res,
               'replies': replies or [], 'settings': settings or {}}
    if save_fail_at is not None:
        payload['saveFailAt'] = save_fail_at
    proc = subprocess.run(['bun', 'tests/splatnet3_hook_driver.ts'], cwd=ROOT,
                          input=json.dumps(payload), text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class SalmonHookTests(unittest.TestCase):
    def test_token_response_fetches_deduplicated_history_and_details(self):
        out = run(replies=[{'status': 200, 'body': history(['d1', 'd1', 'd2'])},
                           {'status': 200, 'body': detail('d1')},
                           {'status': 200, 'body': detail('d2')}])
        self.assertTrue(out['ok'], out)
        self.assertEqual(len(out['requests']), 3)
        for req in out['requests']:
            self.assertEqual(req['url'], 'https://api.lp1.av5ja.srv.nintendo.net/api/graphql')
            self.assertEqual(req['method'], 'POST')
            self.assertEqual(req['headers']['authorization'], 'Bearer synthetic-token')
            self.assertEqual(req['headers']['x-web-view-ver'], VERSION)
        bodies = [json.loads(r['body']) for r in out['requests']]
        self.assertEqual(bodies[0], {'variables': {}, 'extensions': {'persistedQuery': {'version': 1, 'sha256Hash': HISTORY}}})
        self.assertEqual([b['variables']['coopHistoryDetailId'] for b in bodies[1:]], ['d1', 'd2'])
        self.assertTrue(all(b['extensions']['persistedQuery']['sha256Hash'] == DETAIL for b in bodies[1:]))
        summary = out['result']['actions'][0]['json']
        self.assertEqual(summary['acquired'], ['d1', 'd2'])
        self.assertNotIn('synthetic-token', json.dumps(summary))

    def test_match_scoped_player_ids_do_not_stop_later_result_saves(self):
        import base64
        player = lambda match: base64.b64encode(('CoopPlayer-u-123:' + match + ':u-123').encode()).decode()
        first, second = detail('d1', player('20261023T120000_match1')), detail('d2', player('20261023T120100_match2'))
        out = run(replies=[{'status': 200, 'body': history(['d1', 'd2'])},
                           {'status': 200, 'body': first}, {'status': 200, 'body': second}])
        self.assertTrue(out['ok'], out.get('code'))
        self.assertEqual(len(out['saves']), 3)
        self.assertEqual([json.loads(s['contents']) for s in out['saves'][1:]], [first, second])

    def test_version_10_uses_its_own_hashes(self):
        res = response(request={'headers': {'x-web-view-ver': VERSION_10, 'accept-language': 'ja-JP'}})
        out = run(res=res, replies=[{'status': 200, 'body': history(['d1', 'd1', 'd2'])},
                                    {'status': 200, 'body': detail('d1')},
                                    {'status': 200, 'body': detail('d2')}])
        self.assertTrue(out['ok'], out)
        bodies = [json.loads(r['body']) for r in out['requests']]
        self.assertEqual(len(bodies), 3)
        self.assertEqual(bodies[0]['extensions']['persistedQuery']['sha256Hash'], HISTORY_10)
        self.assertEqual([b['variables']['coopHistoryDetailId'] for b in bodies[1:]], ['d1', 'd2'])
        self.assertTrue(all(b['extensions']['persistedQuery']['sha256Hash'] == DETAIL_10 for b in bodies[1:]))
        for req in out['requests']:
            self.assertEqual(req['headers']['x-web-view-ver'], VERSION_10)

    def test_version_10_empty_history_sends_only_history(self):
        res = response(request={'headers': {'x-web-view-ver': VERSION_10, 'accept-language': 'ja-JP'}})
        out = run(res=res, replies=[{'status': 200, 'body': history([])}])
        self.assertTrue(out['ok'], out)
        self.assertEqual(len(out['requests']), 1)

    def test_failed_token_response_does_not_send(self):
        for res in [response(status=401), response(body={}), response(body={'bulletToken': ''})]:
            out = run(res=res)
            self.assertEqual(out['requests'], [])

    def test_unknown_version_does_not_guess_queries(self):
        out = run(res=response(request={'headers': {'x-web-view-ver': 'unknown'}}))
        self.assertEqual(out['requests'], [])
        self.assertEqual(out['code'], 'unsupported-version')

    def test_expired_token_stops_without_retrying(self):
        out = run(replies=[{'status': 200, 'body': history(['d1', 'd2'])}, {'status': 401, 'body': {}}])
        self.assertEqual(len(out['requests']), 2)
        self.assertEqual(out['code'], 'recapture')

    def test_detail_id_mismatch_stops_acquisition(self):
        for body, code in [(detail('wrong'), 'id-mismatch')]:
            out = run(replies=[{'status': 200, 'body': history(['d1', 'd2', 'd3'])},
                               {'status': 200, 'body': detail('d1')}, {'status': 200, 'body': body}])
            self.assertEqual(out['code'], code)
            self.assertEqual(len(out['requests']), 3)

    def test_missing_detail_is_reported_and_next_detail_is_fetched(self):
        out = run(replies=[{'status': 200, 'body': history(['d1', 'd2'])},
                           {'status': 404, 'body': {}}, {'status': 200, 'body': detail('d2')}])
        self.assertTrue(out['ok'], out)
        summary = out['result']['actions'][0]['json']
        self.assertEqual(summary['unavailable'], ['d1'])
        self.assertEqual(summary['acquired'], ['d2'])

    def test_graphql_error_stops_before_details(self):
        out = run(replies=[{'status': 200, 'body': {'errors': [{'message': 'PersistedQueryNotFound'}]}}])
        self.assertEqual(out['code'], 'graphql')
        self.assertEqual(len(out['requests']), 1)

    def test_limit_is_explicit_and_remaining_ids_are_reported(self):
        out = run(settings={'maxResults': 1}, replies=[{'status': 200, 'body': history(['d1', 'd2'])},
                                                      {'status': 200, 'body': detail('d1')}])
        self.assertEqual(len(out['requests']), 2)
        self.assertEqual(out['result']['actions'][0]['json']['remaining'], 1)
        for invalid in [0, 51, -1, 1.5, '1', True]:
            out = run(settings={'maxResults': invalid})
            self.assertEqual(out['requests'], [])
            self.assertEqual(out['code'], 'invalid-limit')

    def test_captured_login_cookie_is_not_forwarded(self):
        res = response()
        res['request']['headers']['cookie'] = 'synthetic-private-cookie'
        out = run(res=res, replies=[{'status': 200, 'body': history([])}])
        self.assertTrue(out['ok'], out)
        self.assertNotIn('cookie', out['requests'][0]['headers'])
        self.assertNotIn('synthetic-private-cookie', json.dumps(out))

    def test_language_comes_from_token_response_or_captured_header(self):
        res = response(body={'bulletToken': 'synthetic-token', 'lang': 'en-GB'})
        out = run(res=res, replies=[{'status': 200, 'body': history([])}])
        self.assertEqual(out['requests'][0]['headers']['accept-language'], 'en-GB')
        res = response()
        res['request']['headers'].pop('accept-language')
        out = run(res=res)
        self.assertEqual(out['requests'], [])
        self.assertEqual(out['code'], 'missing-context')

    def test_null_detail_and_non_json_http_errors(self):
        out = run(replies=[{'status': 200, 'body': history(['d1'])},
                           {'status': 200, 'body': {'data': {'coopHistoryDetail': None}}}])
        self.assertEqual(out['result']['actions'][0]['json']['unavailable'], ['d1'])
        for status, code in [(401, 'recapture'), (403, 'recapture'), (429, 'http'), (503, 'http')]:
            out = run(replies=[{'status': status, 'body': 'not JSON'}])
            self.assertEqual(out['code'], code)
            self.assertEqual(len(out['requests']), 1)

    def test_missing_context_stops_before_fetch(self):
        out = run(res=response(request={'headers': {}}))
        self.assertEqual(out['code'], 'missing-context')
        self.assertEqual(out['requests'], [])


class SalmonSaveTests(unittest.TestCase):
    """Store original responses; only query/file identity and operational checks are needed."""

    HISTORY_TEXT = ' {"data": {"coopResult": {"historyGroups": {"nodes": [\n {"historyDetails": {"nodes": [{"id": "d1"}, {"id": "d2"}]}}]}}}} \n'

    def detail_text(self, id_, player='synthetic-player'):
        return '{ "data": {"coopHistoryDetail": {"id": "%s", "myResult": {"player": {"id": "%s"}}, "extra": 1.0}} }' % (id_, player)

    def replies(self, *details):
        return [{'status': 200, 'body': self.HISTORY_TEXT}] + [{'status': s, 'body': b} for s, b in details]

    def test_saves_original_history_text_then_each_available_detail_text(self):
        d1, d2 = self.detail_text('d1'), self.detail_text('d2')
        out = run(replies=self.replies((200, d1), (200, d2)))
        self.assertTrue(out['ok'], out)
        self.assertEqual([s['contents'] for s in out['saves']], [self.HISTORY_TEXT, d1, d2])
        paths = [s['path'] for s in out['saves']]
        self.assertEqual(paths, ['Salmon Run/history.json', detail_path('d1'), detail_path('d2')])
        self.assertTrue(all(s['storage'] == 'icloud' for s in out['saves']))
        self.assertEqual(len(set(paths)), 3)

    def test_saved_text_has_no_wrapper_or_token(self):
        out = run(replies=self.replies((200, self.detail_text('d1')), (200, self.detail_text('d2'))))
        for save in out['saves']:
            self.assertNotIn('synthetic-token', save['contents'] + save['path'])
            self.assertNotIn('bulletToken', save['contents'])
        for save in out['saves'][1:]:
            parsed = json.loads(save['contents'])
            self.assertEqual(list(parsed), ['data'])
            self.assertEqual(list(parsed['data']), ['coopHistoryDetail'])

    def test_non_error_responses_without_valid_details_are_not_saved(self):
        out = run(replies=self.replies((404, {}), (200, {'data': {'coopHistoryDetail': None}})))
        self.assertTrue(out['ok'], out)
        self.assertEqual([s['contents'] for s in out['saves']], [self.HISTORY_TEXT])

    def test_invalid_or_error_details_are_never_saved(self):
        cases = [(detail('wrong'), 'id-mismatch'),
                 ({'errors': [{'message': 'boom'}]}, 'graphql'), ({'data': {}}, 'invalid-response')]
        for body, code in cases:
            with self.subTest(code=code):
                out = run(replies=self.replies((200, body)))
                self.assertEqual(out['code'], code)
                self.assertEqual([s['contents'] for s in out['saves']], [self.HISTORY_TEXT])
        for status, code in [(401, 'recapture'), (500, 'http')]:
            out = run(replies=self.replies((status, 'not JSON')))
            self.assertEqual(out['code'], code)
            self.assertEqual(len(out['saves']), 1)

    def test_invalid_history_is_not_saved(self):
        for body in ({'errors': [{'message': 'PersistedQueryNotFound'}]}, {'data': {}}, 'not JSON'):
            out = run(replies=[{'status': 200, 'body': body}])
            self.assertFalse(out['ok'], out)
            self.assertEqual(out['saves'], [])
        out = run(replies=[{'status': 503, 'body': 'x'}])
        self.assertEqual(out['saves'], [])

    def test_no_save_without_token_response(self):
        out = run(res=response(status=401))
        self.assertEqual(out['saves'], [])

    def test_sha256_known_vectors_and_python_hashlib_crosscheck(self):
        ids = ['', 'abc', 'd1', 'あ' * 170 + 'ab', 'a/b+c==', '😀' * 100, 'x' * 512, 'y' * 55, 'y' * 56, 'y' * 64]
        out = run(replies=[{'status': 200, 'body': history(['abc'])}, {'status': 200, 'body': detail('abc')}])
        self.assertEqual(out['saves'][1]['path'],
                         'Salmon Run/details/ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad.json')
        for id_ in ids[2:]:
            out = run(replies=[{'status': 200, 'body': history([id_])}, {'status': 200, 'body': detail(id_)}])
            self.assertEqual(out['saves'][1]['path'], detail_path(id_))

    def test_distinct_results_get_distinct_fixed_ascii_paths(self):
        ids = ['a/b', 'a_b', 'a-b', 'A/B', 'a%2Fb', '../x', '..', 'ab/', '/ab']
        out = run(replies=[{'status': 200, 'body': history(ids)}] + [{'status': 200, 'body': detail(i)} for i in ids])
        self.assertTrue(out['ok'], out)
        paths = [s['path'] for s in out['saves'][1:]]
        self.assertEqual(paths, [detail_path(i) for i in ids])
        self.assertEqual(len(set(paths)), len(ids))
        for path in paths:
            self.assertRegex(path, r'^Salmon Run/details/[0-9a-f]{64}\.json$')

    def test_long_result_ids_use_fixed_length_paths(self):
        id_ = 'あ' * 300
        replies = [{'status': 200, 'body': history([id_])}, {'status': 200, 'body': detail(id_)}]
        out = run(replies=replies)
        self.assertTrue(out['ok'], out)
        self.assertEqual(len(out['saves']), 2)
        self.assertEqual(out['saves'][1]['path'], detail_path(id_))
        self.assertEqual(len(out['saves'][1]['path']), len('Salmon Run/details/.json') + 64)

    def test_save_error_on_history_stops_before_any_detail_request(self):
        out = run(replies=self.replies((200, self.detail_text('d1'))), save_fail_at=1)
        self.assertFalse(out['ok'], out)
        self.assertEqual(len(out['requests']), 1)
        self.assertEqual(len(out['saves']), 1)

    def test_save_error_stops_later_work_and_keeps_earlier_saves(self):
        d1 = self.detail_text('d1')
        out = run(replies=self.replies((200, d1), (200, self.detail_text('d2'))), save_fail_at=2)
        self.assertFalse(out['ok'], out)
        self.assertEqual(len(out['requests']), 2)  # history + d1; d2 never requested
        self.assertEqual([s['contents'] for s in out['saves']], [self.HISTORY_TEXT, d1])
        self.assertTrue(out['saves'][1].get('failed'))
