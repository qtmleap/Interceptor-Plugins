"""Schema 2 (four HTTP lifecycle hooks) manifest validation; schema 1 stays byte-compatible."""
import copy
import json
import sys
import unittest

from helpers import REPO
sys.path.insert(0, str(REPO / 'tools'))
import repository_config as config

V2 = {
    "schemaVersion": 2,
    "id": "90A213C0-9D3C-47F5-ABB8-C15C7472E2AE",
    "name": "Search limiter",
    "version": "2.0.0",
    "matches": [{"hosts": ["api.example.com"], "methods": ["POST"], "path": {"kind": "exact", "value": "/search"}}],
    "read": {"metadata": ["host"], "headers": [], "queryKeys": [], "body": {"mode": "json"}},
    "write": {"requestBody": True, "responseBody": False},
    "endpointBindings": ["preview"],
    "settings": {},
}


def v2(**changes):
    manifest = copy.deepcopy(V2)
    manifest.update(changes)
    return manifest


class HTTPHookManifestTests(unittest.TestCase):
    def rejects(self, manifest):
        with self.assertRaises(config.ToolError):
            config.validate_manifest(manifest, 'manifest')

    def test_valid_v2_manifest_is_accepted(self):
        config.validate_manifest(v2(), 'manifest')
        config.validate_manifest(v2(read={"metadata": [], "headers": ["content-type"], "queryKeys": ["q"], "body": {"mode": "none"}},
                                    write={"requestBody": False, "responseBody": False}), 'manifest')
        config.validate_manifest(v2(matches=[{"hosts": ["a.example.com"], "status": {"min": 500, "max": 599}}] * 16), 'manifest')

    def test_optional_publisher_text_matches_native_manifest_fields(self):
        config.validate_manifest(v2(author='Example author', summary='Changes search JSON.'), 'manifest')
        config.validate_manifest(v2(author='あ' * 80, summary='あ' * 280), 'manifest')
        for fields in ({'author': ''}, {'author': ' '}, {'author': 'x' * 81},
                       {'summary': 'x' * 281}, {'summary': 'line\nbreak'}, {'author': None}):
            with self.subTest(fields=fields):
                self.rejects(v2(**fields))

    def test_v2_has_no_subscriptions_and_requires_every_field(self):
        self.rejects(v2(subscriptions=[]))
        for key in ("matches", "read", "write", "endpointBindings", "settings"):
            manifest = v2()
            del manifest[key]
            with self.subTest(key=key):
                self.rejects(manifest)

    def test_matches_are_one_to_sixteen_match_shaped_objects(self):
        match = V2["matches"][0]
        for matches in ([], [match] * 17, [{"methods": ["GET"]}], [dict(match, extra=1)],
                        [dict(match, hosts=["API.example.com"])], [dict(match, methods=["post"])],
                        [dict(match, path={"kind": "glob", "value": "/*"})], [dict(match, status={"min": 600, "max": 700})]):
            with self.subTest(matches=matches):
                self.rejects(v2(matches=matches))

    def test_write_grants_are_exact_booleans(self):
        for write in ({"requestBody": True}, {"requestBody": 1, "responseBody": False},
                      {"requestBody": True, "responseBody": False, "status": True}, [], None):
            with self.subTest(write=write):
                self.rejects(v2(write=write))

    def test_v2_body_modes_are_none_or_json_only(self):
        for body in ({"mode": "raw"}, {"mode": "jsonPointers", "pointers": ["/a"]}, {"mode": "json", "pointers": ["/a"]}):
            with self.subTest(body=body):
                self.rejects(v2(read=dict(V2["read"], body=body)))

    def test_unknown_schema_versions_are_rejected(self):
        for version in (0, 3, True, "2"):
            with self.subTest(version=version):
                self.rejects(v2(schemaVersion=version))

    def test_v1_remains_strict_and_cannot_use_v2_fields(self):
        manifest = {"schemaVersion": 1, "id": V2["id"], "name": "Legacy", "version": "1.0.0",
                    "subscriptions": [{"phase": "request.completed", "match": {"hosts": ["example.com"]}}],
                    "read": {"metadata": ["host"], "headers": [], "queryKeys": [], "body": {"mode": "none"}},
                    "endpointBindings": ["preview"], "settings": {}}
        config.validate_manifest(manifest, 'manifest')
        self.rejects(dict(manifest, matches=[], write={"requestBody": False, "responseBody": False}))
        self.rejects(dict(manifest, read=dict(manifest["read"], body={"mode": "json"})))

    def test_validate_package_accepts_v2(self):
        import repository_tool as tool
        data = config.package_bytes(v2(), 'Interceptor.attach({hosts:["api.example.com"]},{});')
        package = tool.validate_package(data)
        self.assertEqual(package["manifest"]["schemaVersion"], 2)


if __name__ == '__main__':
    unittest.main()
