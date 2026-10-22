"""Optional publisher-declared manifest.publishedAt: strict UTC seconds, copied verbatim, never in the index."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import repository_config as config  # noqa: E402
import repository_tool as tool  # noqa: E402
import route_sources  # noqa: E402

REPOSITORY_ID = "90A213C0-9D3C-47F5-ABB8-C15C7472E2AD"
DATE = "2026-10-21T09:30:00Z"
NOW = 1_792_454_400


def manifest(schema=2, **extra):
    value = {"schemaVersion": schema, "id": "90A213C0-9D3C-47F5-ABB8-C15C7472E2AE", "name": "Search limiter",
             "version": "2.0.0", "read": {"metadata": ["host"], "headers": [], "queryKeys": [], "body": {"mode": "none"}},
             "endpointBindings": [], "settings": {}, **extra}
    if schema == 2:
        value.update(matches=[{"hosts": ["example.com"], "methods": ["GET"], "path": {"kind": "exact", "value": "/"},
                               "hooks": {"request": {"onEnter": "handler.js"}}}],
                     write={"requestBody": False, "responseBody": False})
    else:
        value["subscriptions"] = [{"phase": "request.completed", "match": {"hosts": ["example.com"]}}]
    return value


def package(schema=2, **extra):
    value = manifest(schema, **extra)
    source = "function onRequest(){return {actions:[]}}" if schema == 1 else {"handler.js": "// hook\n"}
    return config.package_bytes(value, source)


class PublicationDateTests(unittest.TestCase):
    def test_shared_grammar_is_the_existing_index_parser(self):
        self.assertIs(tool.parse_time, config.parse_time)
        self.assertEqual(config.parse_time(DATE), tool.parse_time(DATE))
        self.assertEqual(config.parse_time("1970-01-01T00:00:00Z"), 0)

    def test_valid_dates_accepted_for_both_schemas_and_absence_stays_valid(self):
        for schema in (1, 2):
            for date in (DATE, "2024-02-29T23:59:59Z", "0001-01-01T00:00:00Z"):
                with self.subTest(schema=schema, date=date):
                    config.validate_manifest(manifest(schema, publishedAt=date), "manifest")
            config.validate_manifest(manifest(schema), "legacy")

    def test_malformed_dates_rejected_for_both_schemas(self):
        bad = (None, 1, True, [], {}, "", " ", DATE + " ", " " + DATE, "2026-10-21", "2026-10-21T09:30:00",
               "2026-10-21T09:30:00z", "2026-10-21t09:30:00Z", "2026-10-21 09:30:00Z", "2026-10-21T09:30Z",
               "2026-10-21T09:30:00.000Z", "2026-10-21T09:30:00+00:00", "2026-10-21T18:30:00+09:00",
               "2026-02-29T00:00:00Z", "2026-13-01T00:00:00Z", "2026-00-10T00:00:00Z", "2026-10-32T00:00:00Z",
               "2026-10-21T24:00:00Z", "2026-10-21T09:60:00Z", "2026-10-21T09:30:60Z", "0000-01-01T00:00:00Z",
               "2026-10-21T09:30:00Z\n", "２０２６-10-21T09:30:00Z")
        for schema in (1, 2):
            for date in bad:
                with self.subTest(schema=schema, date=repr(date)), self.assertRaises(config.ToolError):
                    config.validate_manifest(manifest(schema, publishedAt=date), "manifest")

    def test_authored_route_metadata_accepts_the_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plugin.json"
            value = manifest(publishedAt=DATE)
            del value["matches"]
            path.write_text(json.dumps(value))
            self.assertEqual(route_sources.metadata(path)["publishedAt"], DATE)
            value["publishedAt"] = "2026-10-21"
            path.write_text(json.dumps(value))
            with self.assertRaises(config.ToolError):
                route_sources.metadata(path)

    def test_date_is_not_display_metadata(self):
        self.assertNotIn("publishedAt", config.DISPLAY_METADATA_KEYS)
        self.assertEqual([key for key, _, _ in config.DISPLAY_METADATA_LIMITS], ["author", "summary", "category"])

    def test_package_bytes_preserve_exact_string_and_are_stable(self):
        for schema in (1, 2):
            first = package(schema, publishedAt=DATE)
            self.assertEqual(json.loads(first)["manifest"]["publishedAt"], DATE)
            self.assertEqual(first, package(schema, publishedAt=DATE))  # no clock input
            self.assertEqual(tool.validate_package(first)["manifest"]["publishedAt"], DATE)

    def test_legacy_package_without_the_field_is_unchanged(self):
        for schema in (1, 2):
            data = package(schema)
            self.assertNotIn(b"publishedAt", data)
            self.assertNotIn("publishedAt", tool.validate_package(data)["manifest"])
            self.assertEqual(data, package(schema))

    def test_package_validation_rejects_a_bad_date(self):
        for schema in (1, 2):
            raw = json.loads(package(schema))
            raw["manifest"]["publishedAt"] = "2026-10-21"
            with self.assertRaises(config.ToolError):
                tool.validate_package(json.dumps(raw).encode())

    def test_index_never_carries_or_accepts_the_date(self):
        data = package(publishedAt=DATE)
        entry = {"id": "90A213C0-9D3C-47F5-ABB8-C15C7472E2AE", "name": "Search limiter", "version": "2.0.0",
                 "packagePath": "plugins/search.json", "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        index = {"schemaVersion": 1, "id": REPOSITORY_ID, "name": "Catalog", "sequence": 1,
                 "issuedAt": "2026-10-20T00:00:00Z", "expiresAt": "2026-11-19T00:00:00Z", "plugins": [dict(entry)]}
        tool.parse_index(index)
        index["plugins"][0]["publishedAt"] = DATE
        with self.assertRaises(config.ToolError):
            tool.parse_index(index)
        tool.validate_package(data, entry)

    def test_publish_binds_the_date_through_package_hash_only(self):
        hashes, sizes = [], []
        for extra in ({}, {"publishedAt": DATE}, {"publishedAt": "2026-10-22T09:30:00Z"}):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "plugins").mkdir()
                data = package(**extra)
                (root / "plugins/search.json").write_bytes(data)
                tool.publish(root, REPOSITORY_ID, "Catalog", 1, None, now=NOW)
                snapshot = tool.verify_envelope((root / "repository.json").read_bytes(), NOW)
                (entry,) = snapshot["index"]["plugins"]
                self.assertNotIn("publishedAt", entry)
                self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
                hashes.append(entry["sha256"])
                sizes.append(entry["size"])
        self.assertEqual(len(set(hashes)), 3)
        self.assertEqual(sizes[1], sizes[0] + len(b',"publishedAt":"' + DATE.encode() + b'"'))
        self.assertEqual(sizes[1], sizes[2])

    def test_existing_limits_are_unchanged(self):
        for key, text in (("author", "x" * 81), ("summary", "x" * 281), ("category", "x" * 81)):
            with self.assertRaises(config.ToolError):
                config.validate_manifest(manifest(publishedAt=DATE, **{key: text}), "manifest")
        with self.assertRaises(config.ToolError):
            config.validate_manifest(manifest(publishedAt=DATE, extra=1), "manifest")


if __name__ == "__main__":
    unittest.main()
