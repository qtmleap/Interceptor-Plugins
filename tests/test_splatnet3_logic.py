import hashlib
import json
import subprocess
import unittest
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DRIVER = REPO / "tests" / "splatnet3_driver.ts"
FIX = REPO / "fixtures" / "splatnet3-salmon"
CATALOG = json.loads((REPO / "docs" / "development" / "splatnet3-queries.json").read_text())
VERSION = "4.0.0-091d4283"
# Expected protocol identifiers from the pinned mapping (4.0.0) and Nintendo public bundle (10.0.0).
# Constants check catalog/hook consistency; provenance and live verification scope are documented separately.
H = "0f8c33970a425683bb1bdecca50a0ca4fb3c3641c0b2a1237aedfde9c0cb2b8f"
D = "824a1e22c4ad4eece7ad94a9a0343ecd76784be4f77d8f6f563c165afc8cf602"
VERSION_10 = "10.0.0-d15503c4"
H10 = "e11a8cf2c3de7348495dea5cdcaa25e0c153541c4ed63f044b6c174bc5b703df"
D10 = "f2d55873a9281213ae27edc171e2b19131b3021a2ae263757543cdd3bf015cc8"
PAIR = {"history": H, "detail": D}


def run(fn, *args):
    p = subprocess.run(["bun", str(DRIVER)], input=json.dumps({"fn": fn, "args": list(args)}), capture_output=True, text=True, cwd=REPO)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def history(*groups, only_first=None):
    def g(ids):
        return {"historyDetails": {"nodes": [{"id": i} for i in ids]}}
    cr = {"historyGroups": {"nodes": [g(x) for x in groups]}}
    if only_first is not None:
        cr["historyGroupsOnlyFirst"] = {"nodes": [g(x) for x in only_first]}
    return {"data": {"coopResult": cr}}


def detail(id_="d1", player="p1"):
    return {"data": {"coopHistoryDetail": {"id": id_, "myResult": {"player": {"id": player}}}}}


class QueryTests(unittest.TestCase):
    def test_plugin_typechecks_with_only_supplied_sdk(self):
        # Ambient website dependencies must not grant Node/DOM APIs to this module.
        with tempfile.TemporaryDirectory(prefix="splatnet3-empty-types-") as empty_types:
            p = subprocess.run(["bun", str(REPO / "node_modules/typescript/bin/tsc"),
                                str(REPO / "plugins/splatnet3-salmon/hooks/api.lp1.av5ja.srv.nintendo.net/api/bullet_tokens/POST.ts"),
                                str(REPO / "types/interceptor.d.ts"),
                                "--strict", "--target", "ES2020", "--lib", "ES2020", "--noEmit",
                                "--module", "esnext", "--moduleResolution", "bundler",
                                "--typeRoots", empty_types], cwd=REPO, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_resolve_supported(self):
        self.assertEqual(run("queriesFor", VERSION), {"ok": True, "value": PAIR})

    def test_missing_vs_unsupported(self):
        self.assertEqual(run("queriesFor", "")["code"], "missing-context")
        self.assertEqual(run("queriesFor", "9.9.9-deadbeef")["code"], "unsupported-version")

    def test_exact_versions_resolve_independently(self):
        self.assertEqual(run("queriesFor", VERSION)["value"], PAIR)
        self.assertEqual(run("queriesFor", VERSION_10)["value"], {"history": H10, "detail": D10})
        for v in ("10.0.0", "10.0.0-D15503C4", "10.0.1-d15503c4"):
            self.assertEqual(run("queriesFor", v)["code"], "unsupported-version")

    def test_inherited_names_are_unsupported(self):
        for v in ("__proto__", "constructor", "toString"):
            self.assertEqual(run("queriesFor", v)["code"], "unsupported-version")

    def test_catalog_matches_documented_hashes(self):
        for version, pair in CATALOG["versions"].items():
            self.assertEqual(run("queriesFor", version)["value"], pair)

    def test_request_bodies(self):
        ext = lambda h: {"persistedQuery": {"version": 1, "sha256Hash": h}}
        self.assertEqual(run("graphqlRequest", H, {})["value"], {"variables": {}, "extensions": ext(H)})
        self.assertEqual(run("detailRequest", PAIR, "synthetic-id")["value"],
                         {"variables": {"coopHistoryDetailId": "synthetic-id"}, "extensions": ext(D)})
        self.assertEqual(run("detailRequest", PAIR, "")["code"], "invalid-id")
        self.assertEqual(run("detailRequest", PAIR, "é" * 257)["code"], "invalid-id")

    def test_detail_path_is_utf8_sha256(self):
        self.assertEqual(run("detailPath", "abc")["value"],
                         "Salmon Run/details/ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad.json")
        for id_ in ("あ" * 170 + "ab", "😀" * 128, "a/b+c==", "é" * 256):
            digest = hashlib.sha256(id_.encode()).hexdigest()
            self.assertEqual(run("detailPath", id_)["value"], f"Salmon Run/details/{digest}.json")


class HistoryTests(unittest.TestCase):
    def ids(self, body):
        return run("historyIDs", body)

    def test_fixture_order_and_dedupe(self):
        body = json.loads((FIX / "history-valid.json").read_text())
        self.assertEqual(self.ids(body)["value"], ["synthetic-detail-1", "synthetic-detail-2", "synthetic-detail-3", "synthetic-detail-4"])

    def test_valid_empty_distinct_from_malformed(self):
        self.assertEqual(self.ids(history())["value"], [])
        self.assertEqual(self.ids(history([]))["value"], [])
        for bad in (None, [], {}, {"data": None}, {"data": {}}, {"data": {"coopResult": None}},
                    {"data": {"coopResult": {}}}, {"data": {"coopResult": {"historyGroups": {"nodes": {}}}}},
                    {"data": {"coopResult": {"historyGroups": {"nodes": [None]}}}},
                    {"data": {"coopResult": {"historyGroups": {"nodes": [{"historyDetails": {}}]}}}},
                    {"data": {"coopResult": {"historyGroups": {"nodes": [{"historyDetails": {"nodes": [None]}}]}}}}):
            self.assertEqual(self.ids(bad)["code"], "invalid-response", bad)

    def test_graphql_errors(self):
        ok = history(["a"])
        self.assertEqual(self.ids({**ok, "errors": [{"message": "x"}]})["code"], "graphql")
        self.assertEqual(self.ids({"errors": [{"message": "x"}]})["code"], "graphql")
        self.assertEqual(self.ids({**ok, "errors": None})["value"], ["a"])
        for bad in ("oops", {}, [], [1]):
            self.assertEqual(self.ids({**ok, "errors": bad})["code"], "invalid-response", bad)

    def test_limits(self):
        self.assertEqual(self.ids(history([f"id{i}" for i in range(250)]))["value"],
                         [f"id{i}" for i in range(250)])
        ids = [f"id{i}" for i in range(256)]
        self.assertEqual(self.ids(history(ids[:100], ids[100:] + ids[:5]))["value"], ids)
        self.assertEqual(self.ids(history(ids + ["extra"]))["code"], "limit")
        self.assertEqual(self.ids(history([f"id{i}" for i in range(257)]))["code"], "limit")
        self.assertEqual(self.ids(history(ids, only_first=["extra"]))["code"], "limit")

    def test_invalid_ids(self):
        for bad in ("", "x" * 513, "é" * 257, 5, None):
            self.assertEqual(self.ids(history([bad]))["code"], "invalid-id", bad)
        self.assertEqual(self.ids(history(["é" * 256]))["value"], ["é" * 256])


class DetailTests(unittest.TestCase):
    """detailAvailable: true when valid, false when the result is gone, else raises a code."""

    def check(self, body, eid="d1"):
        return run("detailAvailable", body, eid)

    def test_valid_and_fixture(self):
        self.assertEqual(self.check(detail()), {"ok": True, "value": True})
        body = json.loads((FIX / "detail-valid.json").read_text())
        self.assertEqual(self.check(body, "synthetic-detail-1"), {"ok": True, "value": True})

    def test_graphql_errors(self):
        self.assertEqual(self.check({"errors": [{"message": "PersistedQueryNotFound"}]})["code"], "query-rejected")
        self.assertEqual(self.check({"errors": [{"message": "boom"}]})["code"], "graphql")
        self.assertEqual(self.check({**detail(), "errors": [{"message": "partial"}]})["code"], "graphql")
        self.assertEqual(self.check({**detail(), "errors": "x"})["code"], "invalid-response")
        self.assertEqual(self.check({**detail(), "errors": None}), {"ok": True, "value": True})

    def test_null_and_malformed(self):
        self.assertEqual(self.check({"data": {"coopHistoryDetail": None}}), {"ok": True, "value": False})
        for bad in (None, "text", [], {}, {"data": None}, {"data": {}}, {"data": {"coopHistoryDetail": "x"}}):
            self.assertEqual(self.check(bad)["code"], "invalid-response", bad)

    def test_id_checks(self):
        self.assertEqual(self.check(detail("other"))["code"], "id-mismatch")
        for bad in (None, "", 5):
            body = detail(); body["data"]["coopHistoryDetail"]["id"] = bad
            self.assertEqual(self.check(body)["code"], "id-mismatch", bad)
        del body["data"]["coopHistoryDetail"]["id"]
        self.assertEqual(self.check(body)["code"], "id-mismatch")

    def test_principal_checks(self):
        for bad in (None, "", "x" * 513, "é" * 257, 7):
            self.assertEqual(self.check(detail(player=bad))["code"], "invalid-principal", bad)
        for mut in (lambda d: d["data"]["coopHistoryDetail"].pop("myResult"),
                    lambda d: d["data"]["coopHistoryDetail"]["myResult"].pop("player")):
            body = detail(); mut(body)
            self.assertEqual(self.check(body)["code"], "invalid-principal")
        self.assertEqual(self.check(detail(player="p2"), "d1")["value"], True)

    def test_errors_never_echo_bodies(self):
        self.assertNotIn("SECRET", json.dumps(self.check({"errors": [{"message": "SECRET-TOKEN"}]})))


if __name__ == "__main__":
    unittest.main()
