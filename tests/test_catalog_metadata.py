"""Publisher display metadata stays optional, bounded and consistent across package/feed boundaries."""
import copy
import hashlib
import json
import sys

from helpers import Case, REPO, OFFICIAL_REPOSITORY_ID

sys.path.insert(0, str(REPO / 'tools'))
import repository_config as config
import repository_tool as tool
import route_sources
import setup as setup_tool


class CatalogMetadataTests(Case):
    def manifest(self, schema=2, **metadata):
        value = {
            'schemaVersion': schema, 'id': '90A213C0-9D3C-47F5-ABB8-C15C7472E2AE',
            'name': 'Search limiter', 'version': '2.0.0',
            'read': {'metadata': ['host'], 'headers': [], 'queryKeys': [], 'body': {'mode': 'none'}},
            'endpointBindings': [], 'settings': {}, **metadata,
        }
        if schema == 2:
            value.update(matches=[{'hosts': ['example.com'], 'methods': ['GET'],
                                  'path': {'kind': 'exact', 'value': '/'},
                                  'hooks': {'request': {'onEnter': 'handler.js'}}}],
                         write={'requestBody': False, 'responseBody': False})
        else:
            value['subscriptions'] = [{'phase': 'request.completed', 'match': {'hosts': ['example.com']}}]
        return value

    def package(self, **metadata):
        return json.dumps({'manifest': self.manifest(schema=1, **metadata),
                           'source': 'function onRequest(){return {actions:[]}}'}, ensure_ascii=False).encode()

    def entry(self, data, **metadata):
        return {'id': '90A213C0-9D3C-47F5-ABB8-C15C7472E2AE', 'name': 'Search limiter',
                'version': '2.0.0', 'packagePath': 'plugins/search.json',
                'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data), **metadata}

    def index(self, entry):
        return {'schemaVersion': 1, 'id': OFFICIAL_REPOSITORY_ID, 'name': 'Catalog', 'sequence': 1,
                'issuedAt': '2026-10-20T00:00:00Z', 'expiresAt': '2026-11-19T00:00:00Z',
                'plugins': [entry]}

    def test_category_is_optional_and_preserved_verbatim_for_both_manifest_versions(self):
        for schema in (1, 2):
            value = self.manifest(schema, category='  Requests / リクエスト  ')
            config.validate_manifest(value, 'manifest')
            self.assertEqual(value['category'], '  Requests / リクエスト  ')
            config.validate_manifest(self.manifest(schema), 'legacy metadata omission')

    def test_category_counts_unicode_scalars_and_utf8_bytes(self):
        for category in ('a' * 80, 'あ' * 80, '😀' * 64, 'e\u0301' * 40):
            with self.subTest(category=category):
                config.validate_manifest(self.manifest(category=category), 'manifest')
        for category in ('a' * 81, '😀' * 65, 'e\u0301' * 40 + 'e'):
            with self.subTest(category=category), self.assertRaises(config.ToolError):
                config.validate_manifest(self.manifest(category=category), 'manifest')

    def test_category_rejects_wrong_types_blank_and_prohibited_unicode(self):
        for category in (None, 1, [], {}, '', ' ', '\u00a0\u3000', 'line\nbreak',
                         'x\u0085y', 'x\u202ey', 'x\u200dy', 'x\u2028y', 'x\u2029y', '\ud800'):
            with self.subTest(category=repr(category)), self.assertRaises(config.ToolError):
                config.validate_manifest(self.manifest(category=category), 'manifest')

    def test_authored_route_metadata_accepts_category_without_permitting_routes(self):
        path = self.tmp / 'plugin.json'
        value = self.manifest(category='Requests')
        del value['matches']
        path.write_text(json.dumps(value))
        self.assertEqual(route_sources.metadata(path)['category'], 'Requests')
        value['matches'] = []
        path.write_text(json.dumps(value))
        with self.assertRaises(config.ToolError):
            route_sources.metadata(path)

    def test_index_retains_each_optional_metadata_field_and_accepts_legacy_omission(self):
        data = self.package()
        for metadata in ({}, {'author': ' Example Team '}, {'summary': 'Changes search JSON.'},
                         {'category': 'Requests / リクエスト'},
                         {'author': 'Example Team', 'summary': 'Changes search JSON.', 'category': 'Requests'}):
            with self.subTest(metadata=metadata):
                entry = self.entry(data, **metadata)
                parsed = tool.parse_index(self.index(entry))['plugins'][0]
                self.assertEqual(parsed, entry)

    def test_index_metadata_uses_the_same_display_text_limits(self):
        data = self.package()
        for field, values in {
            'author': (None, '', ' ', 'x' * 81, '😀' * 65, '\u202eExample'),
            'summary': (False, '', 'x' * 281, '😀' * 257, 'line\nbreak'),
            'category': ([], '\u3000', 'x' * 81, '😀' * 65, 'e\u0301' * 40 + 'e', 'x\u2028y'),
        }.items():
            for value in values:
                with self.subTest(field=field, value=repr(value)), self.assertRaises(config.ToolError):
                    tool.parse_index(self.index(self.entry(data, **{field: value})))

    def test_unknown_index_fields_and_versions_stay_rejected(self):
        data = self.package()
        for extra in ({'hosts': ['example.com']}, {'categories': ['Requests']}, {'extra': True}):
            with self.subTest(extra=extra), self.assertRaises(config.ToolError):
                tool.parse_index(self.index(self.entry(data, **extra)))
        index = self.index(self.entry(data))
        index['schemaVersion'] = 2
        with self.assertRaises(config.ToolError):
            tool.parse_index(index)

    def test_present_index_metadata_must_match_the_manifest_exactly(self):
        metadata = {'author': 'Example Team', 'summary': 'Changes search JSON.', 'category': 'Requests'}
        data = self.package(**metadata)
        tool.validate_package(data, self.entry(data, **metadata))
        tool.validate_package(data, self.entry(data))
        for field in metadata:
            changed = dict(metadata, **{field: 'Other value'})
            with self.subTest(field=field), self.assertRaises(config.ToolError):
                tool.validate_package(data, self.entry(data, **changed))
        # Canonically equivalent text is still different publisher-supplied bytes.
        data = self.package(author='Café')
        with self.assertRaises(config.ToolError):
            tool.validate_package(data, self.entry(data, author='Cafe\u0301'))

    def test_index_metadata_cannot_claim_a_field_missing_from_the_manifest(self):
        data = self.package()
        for field in ('author', 'summary', 'category'):
            for claim in ('Unpublished claim', None):
                with self.subTest(field=field, claim=claim), self.assertRaises(config.ToolError):
                    tool.validate_package(data, self.entry(data, **{field: claim}))

    def test_publisher_copies_only_present_metadata_and_preserves_legacy_entries(self):
        output = self.tmp / 'catalog'
        (output / 'plugins').mkdir(parents=True)
        metadata = {'author': ' Example Team ', 'summary': 'Changes search JSON.', 'category': 'Requests'}
        data = self.package(**metadata)
        (output / 'plugins/search.json').write_bytes(data)
        tool.publish(output, OFFICIAL_REPOSITORY_ID, 'Catalog', 1, None, now=1_792_454_400)
        snapshot = tool.verify_envelope((output / 'repository.json').read_bytes(), 1_792_454_400)
        self.assertEqual(snapshot['index']['plugins'], [self.entry(data, **metadata)])
        tool.validate_package(data, snapshot['index']['plugins'][0])
        legacy = self.package()
        (output / 'plugins/search.json').write_bytes(legacy)
        tool.publish(output, OFFICIAL_REPOSITORY_ID, 'Catalog', 2, None, now=1_792_454_400)
        snapshot = tool.verify_envelope((output / 'repository.json').read_bytes(), 1_792_454_400)
        self.assertEqual(snapshot['index']['plugins'], [self.entry(legacy)])

    def test_setup_checkpoint_preserves_authored_display_metadata(self):
        root = self.make_root()
        path = root / 'plugins/demo/plugin.json'
        path.parent.mkdir(parents=True)
        metadata = self.manifest(author='Example Team', summary='Changes search JSON.', category=' Requests ')
        del metadata['matches']
        path.write_text(json.dumps(metadata))
        files = {'repository-config.json': self.config(root), 'plugins/demo/plugin.json': metadata}
        state = {'files': copy.deepcopy(files),
                 'originals': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}}
        setup_tool.check_files(root, state, apply=True)
        self.assertEqual(json.loads(path.read_text()), metadata)
        setup_tool.check_files(root, state, apply=True)
