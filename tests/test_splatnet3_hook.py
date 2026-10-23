import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path(os.environ.get('SPLATNET3_TEST_SOURCE', str(ROOT / 'plugins/splatnet3-salmon/hooks/api.lp1.av5ja.srv.nintendo.net/api/bullet_tokens/POST.ts')))
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


def run(res=None, replies=None, settings=None):
    payload = {'source': str(SOURCE), 'response': response() if res is None else res,
               'replies': replies or [], 'settings': settings or {}}
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

    def test_detail_id_and_account_mismatch_stop_acquisition(self):
        for body, code in [(detail('wrong'), 'id-mismatch'), (detail('d2', 'other-player'), 'principal-mismatch')]:
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

    def test_invalid_tokens_and_missing_context_stop_before_fetch(self):
        for token in ['bad\r\ntoken', 'bad token', 'x' * 4097]:
            out = run(res=response(body={'bulletToken': token}))
            self.assertEqual(out['code'], 'invalid-token')
            self.assertEqual(out['requests'], [])
        out = run(res=response(request={'headers': {}}))
        self.assertEqual(out['code'], 'missing-context')
        self.assertEqual(out['requests'], [])
