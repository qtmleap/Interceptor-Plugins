"""Acquisition uses IDs and transport state without validating gameplay payloads."""
import unittest

import test_splatnet3_hook as fx


def setUpModule():
    fx.setUpModule()


class MinimalAcquisitionTests(unittest.TestCase):
    def test_detail_without_player_fields_is_saved_unchanged(self):
        raw = ' {"data":{"coopHistoryDetail":{"id":"d1","unknownField":{"value":1.0}}}}\n'
        out = fx.run(replies=[{'status': 200, 'body': fx.history(['d1'])}, {'status': 200, 'body': raw}])
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['saves'][1]['contents'], raw)
        self.assertEqual(out['result']['actions'][0]['json']['acquired'], ['d1'])

    def test_unconsumed_player_shapes_do_not_block_acquisition(self):
        for player in [None, {}, {'id': 7}, {'id': ''}]:
            with self.subTest(player=player):
                body = {'data': {'coopHistoryDetail': {'id': 'd1', 'myResult': {'player': player}}}}
                out = fx.run(replies=[{'status': 200, 'body': fx.history(['d1'])}, {'status': 200, 'body': body}])
                self.assertTrue(out['ok'], out)
                self.assertEqual(out['saves'][1]['path'], fx.detail_path('d1'))

    def test_more_than_256_history_ids_still_fetches_only_configured_limit(self):
        ids = [f'd{i}' for i in range(300)]
        out = fx.run(settings={'maxResults': 2}, replies=[{'status': 200, 'body': fx.history(ids + ids[:3])},
                     {'status': 200, 'body': fx.detail(ids[0])}, {'status': 200, 'body': fx.detail(ids[1])}])
        self.assertTrue(out['ok'], out)
        self.assertEqual(len(out['requests']), 3)
        self.assertEqual(len(out['saves']), 3)
        self.assertEqual(out['result']['actions'][0]['json']['remaining'], 298)

    def test_opaque_id_over_512_utf8_bytes_keeps_its_digest_filename(self):
        identifier = 'あ' * 300
        out = fx.run(replies=[{'status': 200, 'body': fx.history([identifier])},
                             {'status': 200, 'body': fx.detail(identifier)}])
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['saves'][1]['path'], fx.detail_path(identifier))

    def test_empty_graphql_errors_do_not_block_valid_data(self):
        out = fx.run(replies=[{'status': 200, 'body': {**fx.history(['d1']), 'errors': []}},
                             {'status': 200, 'body': {**fx.detail('d1'), 'errors': []}}])
        self.assertTrue(out['ok'], out)
        self.assertEqual(len(out['saves']), 2)


if __name__ == '__main__':
    unittest.main()
