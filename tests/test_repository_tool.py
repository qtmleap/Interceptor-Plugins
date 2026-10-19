"""Portable repository tool: real temporary Ed25519 keys, tampering, time rules and strict parsing."""
import base64
import hashlib
import json
import shlex
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

from helpers import Case, REPO, OFFICIAL_REPOSITORY_ID

sys.path.insert(0, str(REPO / "tools"))
import repository_tool as tool  # noqa: E402
from repository_config import ToolError  # noqa: E402

HAS_RUNTIME = shutil.which("bun") is not None or shutil.which("node") is not None
NAME = "Tool fixture"


@unittest.skipUnless(HAS_RUNTIME, "Bun or Node.js is required for Ed25519")
class RepositoryToolTests(Case):
    def key(self, name="repository.key"):
        directory = self.tmp / "keys"
        directory.mkdir(exist_ok=True)
        path = directory / name
        tool.keygen(path)
        return path

    def published(self, key=None, sequence=1, now=None):
        """A root plus a published directory built from its manifests and scripts."""
        root = self.make_root()
        out = self.tmp / f"out-{len(list(self.tmp.iterdir()))}"
        (out / "plugins").mkdir(parents=True)
        for manifest_path in sorted((root / "manifests").glob("*.json")):
            manifest = json.loads(manifest_path.read_text())
            source = (root / "scripts" / (manifest_path.stem + ".js")).read_text()
            (out / "plugins" / manifest_path.name).write_bytes(tool.canonical({"manifest": manifest, "source": source}))
        tool.publish(out, OFFICIAL_REPOSITORY_ID, NAME, sequence, key, now=now)
        if key is not None:
            self.write_config(root, publicKeyFingerprint=tool.fingerprint_of(tool.public_key(tool.read_seed(key))))
        return root, out

    def cli(self, *args):
        return subprocess.run([sys.executable, str(REPO / "tools/repository_tool.py"), *map(str, args)],
                              capture_output=True, text=True, timeout=60)

    # ---- keys

    def test_key_is_raw_seed_0600_and_never_overwritten(self):
        path = self.key()
        self.assertEqual(len(path.read_bytes()), 32)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        original = path.read_bytes()
        with self.assertRaises(ToolError):
            tool.keygen(path)
        self.assertEqual(path.read_bytes(), original)

    def test_key_must_be_owner_only_regular_and_32_bytes(self):
        path = self.key()
        path.chmod(0o644)
        with self.assertRaises(ToolError):
            tool.read_seed(path)
        path.chmod(0o600)
        link = path.with_name("link.key")
        link.symlink_to(path)
        with self.assertRaises(ToolError):
            tool.read_seed(link)
        short = path.with_name("short.key")
        short.write_bytes(b"x" * 31)
        short.chmod(0o600)
        with self.assertRaises(ToolError):
            tool.read_seed(short)

    def test_key_inside_git_checkout_or_public_directory_is_refused(self):
        checkout = self.tmp / "checkout"
        (checkout / ".git").mkdir(parents=True)
        with self.assertRaises(ToolError):
            tool.keygen(checkout / "k")
        public = self.tmp / "Public"
        public.mkdir()
        with self.assertRaises(ToolError):
            tool.keygen(public / "k")

    def test_rfc8032_vector_fingerprint(self):
        seed = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
        expected = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        self.assertEqual(tool.public_key(seed), expected)
        signature = tool.sign(seed, b"")
        self.assertTrue(tool.signature_valid(expected, signature, b""))
        self.assertFalse(tool.signature_valid(expected, signature, b"x"))

    # ---- publish / verify-local

    def test_signed_roundtrip_and_cli(self):
        key = self.key()
        root, out = self.published(key)
        summary = json.loads(tool.verify_local(root, out, True))
        self.assertEqual(summary["sequence"], 1)
        self.assertEqual(summary["plugins"], 2)
        self.assertTrue(summary["signed"])
        self.assertEqual(summary["fingerprint"], self.config(root)["publicKeyFingerprint"])
        proc = self.cli("verify-local", root, out, "--signed")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.cli("fingerprint", key).stdout.strip(), summary["fingerprint"])

    def test_unsigned_roundtrip_but_signed_is_demanded(self):
        root, out = self.published()
        self.assertFalse(json.loads(tool.verify_local(root, out, False))["signed"])
        self.write_config(root, publicKeyFingerprint="c" * 64)
        with self.assertRaises(ToolError):
            tool.verify_local(root, out, True)

    def test_envelope_layout_matches_the_app(self):
        key = self.key()
        _, out = self.published(key)
        envelope = json.loads((out / "repository.json").read_text())
        self.assertEqual(set(envelope), {"schemaVersion", "payload", "signature"})
        self.assertEqual(set(envelope["signature"]), {"algorithm", "publicKey", "value"})
        payload = base64.b64decode(envelope["payload"])
        index = json.loads(payload)
        self.assertEqual(payload, tool.canonical(index))
        self.assertEqual(index["expiresAt"] > index["issuedAt"], True)
        signature = base64.b64decode(envelope["signature"]["value"])
        public = base64.b64decode(envelope["signature"]["publicKey"])
        self.assertTrue(tool.signature_valid(public, signature, b"InterceptorRepository/v1\x00" + payload))
        for entry in index["plugins"]:
            data = (out / entry["packagePath"]).read_bytes()
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(entry["size"], len(data))

    def test_tampering_is_rejected(self):
        key = self.key()
        root, out = self.published(key)
        package = next((out / "plugins").iterdir())
        original = package.read_bytes()
        package.write_bytes(original.replace(b"onRe", b"onXe", 1))
        with self.assertRaises(ToolError):
            tool.verify_local(root, out, True)
        package.write_bytes(original)
        tool.verify_local(root, out, True)
        envelope = json.loads((out / "repository.json").read_text())
        payload = json.loads(base64.b64decode(envelope["payload"]))
        payload["sequence"] = 2
        envelope["payload"] = base64.b64encode(tool.canonical(payload)).decode()
        (out / "repository.json").write_text(json.dumps(envelope))
        with self.assertRaisesRegex(ToolError, "signature"):
            tool.verify_local(root, out, True)

    def test_wrong_key_and_wrong_repository_are_rejected(self):
        root, out = self.published(self.key())
        self.write_config(root, publicKeyFingerprint="d" * 64)
        with self.assertRaisesRegex(ToolError, "fingerprint"):
            tool.verify_local(root, out, True)
        root, out = self.published(self.key("second.key"))
        self.write_config(root, id="11111111-2222-4333-8444-555555555555")
        with self.assertRaisesRegex(ToolError, "id"):
            tool.verify_local(root, out, True)

    def test_extra_or_missing_package_files_are_rejected(self):
        root, out = self.published()
        (out / "plugins" / "extra.json").write_text("{}")
        with self.assertRaises(ToolError):
            tool.verify_local(root, out, False)

    def test_publish_refuses_key_inside_published_directory(self):
        root, out = self.published()
        key = out / "inside.key"
        key.write_bytes(os.urandom(32))
        key.chmod(0o600)
        with self.assertRaises(ToolError):
            tool.publish(out, OFFICIAL_REPOSITORY_ID, NAME, 2, key)

    def test_publish_rejects_bad_sequence_name_and_arguments(self):
        for args in (("--sequence", "0"), ("--sequence", "9007199254740992"), ("--sequence", "1.5"), ("--sequence", "-1")):
            proc = self.cli("publish", self.tmp, "--id", OFFICIAL_REPOSITORY_ID, "--name", NAME, *args)
            self.assertNotEqual(proc.returncode, 0)
            self.assertNotIn("Traceback", proc.stderr)
        proc = self.cli("publish", self.tmp, "--id", "nope", "--name", NAME, "--sequence", "1")
        self.assertNotEqual(proc.returncode, 0)

    def test_publish_leaves_existing_feed_on_failure(self):
        root, out = self.published()
        before = (out / "repository.json").read_bytes()
        (out / "plugins" / "bad.json").write_text("{not json")
        with self.assertRaises(ToolError):
            tool.publish(out, OFFICIAL_REPOSITORY_ID, NAME, 2, None)
        self.assertEqual((out / "repository.json").read_bytes(), before)
        self.assertEqual([p.name for p in out.iterdir() if p.name.startswith(".")], [])

    # ---- time rules

    def test_time_rules(self):
        now = 1_800_000_000
        index = {"issuedAt": now, "expiresAt": now + 30 * 86400}
        tool.check_time(index, now)
        tool.check_time({"issuedAt": now + 300, "expiresAt": now + 86400}, now)
        for bad in ({"issuedAt": now + 301, "expiresAt": now + 86400},
                    {"issuedAt": now - 100, "expiresAt": now},
                    {"issuedAt": now - 100, "expiresAt": now - 100},
                    {"issuedAt": now, "expiresAt": now + 90 * 86400 + 1}):
            with self.assertRaises(ToolError):
                tool.check_time(bad, now)
        tool.check_time({"issuedAt": now, "expiresAt": now + 90 * 86400}, now)

    def test_expired_feed_fails_local_but_previous_accepts_it(self):
        key = self.key()
        issued = int(time.time()) - 40 * 86400
        root = self.make_root()
        out = self.tmp / "old"
        (out / "plugins").mkdir(parents=True)
        for manifest_path in sorted((root / "manifests").glob("*.json")):
            manifest = json.loads(manifest_path.read_text())
            source = (root / "scripts" / (manifest_path.stem + ".js")).read_text()
            (out / "plugins" / manifest_path.name).write_bytes(tool.canonical({"manifest": manifest, "source": source}))
        # Publishing verifies at its own issue time, so an old issue time is a valid prior feed.
        tool.publish(out, OFFICIAL_REPOSITORY_ID, NAME, 7, key, now=issued)
        self.write_config(root, publicKeyFingerprint=tool.fingerprint_of(tool.public_key(tool.read_seed(key))))
        with self.assertRaisesRegex(ToolError, "expired"):
            tool.verify_local(root, out, True)
        self.assertEqual(tool.previous(root, out / "repository.json"), "7")
        # A prior feed need not contain the same plugin set.
        (root / "manifests" / "server-error-filter.json").unlink()
        (root / "scripts" / "server-error-filter.js").unlink()
        self.assertEqual(tool.previous(root, out / "repository.json"), "7")

    def test_previous_rejects_future_unsigned_wrong_key_and_wrong_id(self):
        key = self.key()
        root, out = self.published(key)
        feed = out / "repository.json"
        self.assertEqual(tool.previous(root, feed), "1")
        future, future_out = self.published(key, now=int(time.time()) + 3600)
        with self.assertRaisesRegex(ToolError, "future"):
            tool.previous(future, future_out / "repository.json")
        unsigned_root, unsigned_out = self.published()
        self.write_config(unsigned_root, publicKeyFingerprint="e" * 64)
        with self.assertRaises(ToolError):
            tool.previous(unsigned_root, unsigned_out / "repository.json")
        self.write_config(root, publicKeyFingerprint="f" * 64)
        with self.assertRaisesRegex(ToolError, "fingerprint"):
            tool.previous(root, feed)
        self.write_config(root, publicKeyFingerprint=tool.fingerprint_of(tool.public_key(tool.read_seed(key))),
                          id="11111111-2222-4333-8444-555555555555")
        with self.assertRaisesRegex(ToolError, "id"):
            tool.previous(root, feed)

    def test_previous_requires_a_configured_fingerprint(self):
        root, out = self.published(self.key())
        self.write_config(root, publicKeyFingerprint=None)
        with self.assertRaises(ToolError):
            tool.previous(root, out / "repository.json")

    # ---- strictness

    def test_strict_json_rejects_hostile_documents(self):
        for bad in (b'{"a":1,"a":2}', b"\xef\xbb\xbf{}", b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}',
                    b'{"a":9007199254740992}', b'["\\ud800"]', b"[1,]", b"\xff", b'{"a":"\x01"}',
                    b"[" * 65 + b"]" * 65, b"[" * 100000):
            with self.assertRaises(ToolError, msg=bad[:20]):
                tool.strict_json(bad)
        self.assertEqual(tool.strict_json(b"[" * 64 + b"]" * 64), json.loads("[" * 64 + "]" * 64))

    def test_strict_base64_and_timestamps(self):
        for bad in ("QQ", "QQ==\n", "QR==", "QQ=", "Q Q=", "é"):
            with self.assertRaises(ToolError, msg=bad):
                tool.strict_base64(bad)
        self.assertEqual(tool.strict_base64("QQ=="), b"A")
        self.assertEqual(tool.parse_time("2026-02-28T23:59:59Z"), 1_772_323_199)
        for bad in ("2026-02-29T00:00:00Z", "2026-13-01T00:00:00Z", "2026-01-01T24:00:00Z",
                    "2026-01-01 00:00:00Z", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00.5Z", "0000-01-01T00:00:00Z"):
            self.assertIsNone(tool.parse_time(bad), bad)
        self.assertEqual(tool.parse_time("2024-02-29T00:00:00Z"), 1_709_164_800)

    def test_unknown_envelope_and_index_fields_are_rejected(self):
        root, out = self.published()
        envelope = json.loads((out / "repository.json").read_text())
        for mutate in (lambda e: e.update(extra=1), lambda e: e.update(schemaVersion=2),
                       lambda e: e.update(schemaVersion=True), lambda e: e.update(signature={"algorithm": "ed25519"})):
            changed = json.loads(json.dumps(envelope))
            mutate(changed)
            with self.assertRaises(ToolError):
                tool.verify_envelope(json.dumps(changed).encode(), time.time())
        payload = json.loads(base64.b64decode(envelope["payload"]))
        for mutate in (lambda p: p.update(extra=1), lambda p: p.update(sequence=0), lambda p: p.update(sequence=True),
                       lambda p: p["plugins"][0].update(packagePath="../x.json"),
                       lambda p: p["plugins"][0].update(sha256="A" * 64),
                       lambda p: p["plugins"][0].update(size=0),
                       lambda p: p["plugins"][0].update(version="01.0.0"),
                       lambda p: p["plugins"].append(dict(p["plugins"][0]))):
            changed = json.loads(json.dumps(payload))
            mutate(changed)
            data = dict(envelope, payload=base64.b64encode(json.dumps(changed).encode()).decode())
            with self.assertRaises(ToolError):
                tool.verify_envelope(json.dumps(data).encode(), time.time())

    def test_canonical_json_sorts_by_utf8_and_escapes_minimally(self):
        self.assertEqual(tool.canonical({"b": 1, "a": [True, None, 1.5], "é": "\x01\"/é"}),
                         '{"a":[true,null,1.5],"b":1,"é":"\\u0001\\"/é"}'.encode())
        self.assertFalse(tool.same_json(1, True))
        self.assertFalse(tool.same_json(1, 1.0))
        self.assertTrue(tool.same_json({"a": [1, "x"]}, {"a": [1, "x"]}))

    def test_package_validation_checks_size_hash_and_metadata(self):
        root, out = self.published()
        entry = json.loads(base64.b64decode(json.loads((out / "repository.json").read_text())["payload"]))["plugins"][0]
        data = (out / entry["packagePath"]).read_bytes()
        tool.validate_package(data, entry)
        for change in ({"size": entry["size"] + 1}, {"sha256": "0" * 64}, {"name": "other"}, {"version": "9.9.9"},
                       {"id": "11111111-2222-4333-8444-555555555555"}):
            with self.assertRaises(ToolError):
                tool.validate_package(data, dict(entry, **change))

    # ---- samples (a stub simulator stands in for the Rust binary; exit codes are the contract)

    def samples_fixture(self, exit_code, stdout):
        root, out = self.published()
        manifests = sorted(p.stem for p in (root / "manifests").glob("*.json"))
        cases = [{"name": "case " + name, "plugin": name, "hook": "request",
                  "event": {"id": "x"}, "expected": {"actions": []}} for name in manifests]
        stub = self.tmp / "stub-simulator"
        text = stdout if isinstance(stdout, str) else json.dumps(stdout)
        stub.write_text('#!/bin/sh\n[ "$1" = run ] || exit 4\nprintf \'%s\' ' + shlex.quote(text) + '\nexit ' + str(exit_code) + '\n')
        stub.chmod(0o755)
        (root / "fixtures" / "cases.json").write_text(json.dumps(cases))
        (root / "fixtures" / "config.json").write_text("{}")
        return root, out, stub

    def run_samples(self, root, out, stub):
        old = os.environ.get("INTERCEPTOR_SIMULATOR")
        os.environ["INTERCEPTOR_SIMULATOR"] = str(stub)
        try:
            return tool.samples(root, out)
        finally:
            if old is None:
                del os.environ["INTERCEPTOR_SIMULATOR"]
            else:
                os.environ["INTERCEPTOR_SIMULATOR"] = old

    def test_samples_compare_output_and_map_exit_codes(self):
        root, out, stub = self.samples_fixture(0, {"actions": []})
        self.assertIn("2 cases", self.run_samples(root, out, stub))
        root, out, stub = self.samples_fixture(0, {"actions": [1]})
        with self.assertRaisesRegex(ToolError, "sample cases failed"):
            self.run_samples(root, out, stub)
        root, out, stub = self.samples_fixture(6, "")
        with self.assertRaisesRegex(ToolError, "sample cases failed"):
            self.run_samples(root, out, stub)
        root, out, stub = self.samples_fixture(7, "")
        with self.assertRaisesRegex(ToolError, "status 7"):
            self.run_samples(root, out, stub)

    def test_sample_judgment_distinguishes_invalid_input_from_script_error(self):
        failures = []
        case = {"name": "invalid event", "expectError": "invalidInput"}
        tool._judge(case, 4, b"", failures)
        self.assertEqual(failures, [])
        tool._judge(case, 6, b"", failures)
        self.assertEqual(failures, ["invalid event: unexpected scriptError"])
        failures.clear()
        tool._judge(case, 0, b'{"actions":[]}', failures)
        self.assertIn("expected invalidInput", failures[0])

    def test_samples_accept_expected_script_errors_and_require_full_coverage(self):
        root, out, stub = self.samples_fixture(6, "")
        cases = json.loads((root / "fixtures" / "cases.json").read_text())
        for case in cases:
            del case["expected"]
            case["expectError"] = "scriptError"
        (root / "fixtures" / "cases.json").write_text(json.dumps(cases))
        self.run_samples(root, out, stub)
        (root / "fixtures" / "cases.json").write_text(json.dumps(cases[:1]))
        with self.assertRaisesRegex(ToolError, "cover every package"):
            self.run_samples(root, out, stub)

    # ---- live URL construction (network paths are exercised by tools/tests/test_fetch_previous.py)

    def test_package_url_stays_beside_the_feed_and_rejects_traversal(self):
        feed = "https://qtmleap.github.io/Interceptor-Plugins/repository.json"
        self.assertEqual(tool.package_url(feed, "plugins/a.json"),
                         "https://qtmleap.github.io/Interceptor-Plugins/plugins/a.json")
        for bad in ("../a.json", "plugins//a.json", "/a.json", "plugins/a b.json", "plugins/%2e%2e"):
            with self.assertRaises(ToolError):
                tool.package_url(feed, bad)

    def test_live_fetch_refuses_plain_http(self):
        root, _ = self.published(self.key())
        self.write_config(root, repositoryURL="http://example.com/repository.json")
        with self.assertRaises(ToolError):
            tool.verify_live(root, 1)

    def test_settings_depth_matches_app_limit(self):
        root, out = self.published()
        package = json.loads(next((out / 'plugins').glob('*.json')).read_text())
        settings = {}
        for _ in range(16):
            settings = {'child': settings}
        package['manifest']['settings'] = settings
        with self.assertRaises(ToolError):
            tool.validate_package(json.dumps(package).encode())

    def test_canonically_equivalent_duplicate_keys_match_swift_rejection(self):
        with self.assertRaises(ToolError):
            tool.strict_json('{"é": 1, "e\\u0301": 2}'.encode())


if __name__ == "__main__":
    unittest.main()
