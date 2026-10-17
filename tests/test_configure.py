import json
import os
import subprocess
import unittest
from pathlib import Path

from helpers import (Case, FP_A, FP_B, OFFICIAL_PLUGIN_IDS, OFFICIAL_REPOSITORY_ID, OFFICIAL_URL, UPSTREAM, tree_digest)

NEW_URL = "https://example-owner.github.io/my-plugins/repository.json"


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class ConfigureTests(Case):
    def configure(self, root, repo="alice/my-plugins", name="Alice plugins", url=NEW_URL, *extra):
        return self.run_tool(root, "configure", "--repository", repo, "--name", name, "--url", url, *extra)

    def test_template_configuration(self):
        root = self.make_root()
        reserved_before = self.reserved_path(root).read_bytes()
        scripts_before = tree_digest(root / "scripts")
        self.ok(self.configure(root))
        cfg = self.config(root)
        self.assertEqual(cfg["githubRepository"], "alice/my-plugins")
        self.assertEqual(cfg["name"], "Alice plugins")
        self.assertEqual(cfg["repositoryURL"], NEW_URL)
        self.assertIsNone(cfg["publicKeyFingerprint"])
        self.assertEqual(cfg["upstreamRevision"], UPSTREAM)
        self.assertEqual(cfg["schemaVersion"], 1)
        reserved = set(json.loads(reserved_before)["ids"])
        new_ids = [cfg["id"]] + self.manifest_ids(root)
        self.assertEqual(len(set(i.upper() for i in new_ids)), 3)
        for i in new_ids:
            self.assertRegex(i, r"^[0-9A-F]{8}-[0-9A-F]{4}-4[0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$")
            self.assertNotIn(i.upper(), {r.upper() for r in reserved})
        self.assertEqual(self.reserved_path(root).read_bytes(), reserved_before, "reserved entries are retained")
        self.assertEqual(tree_digest(root / "scripts"), scripts_before, "source preserved")
        # Everything but the IDs in the manifests is preserved and the result still builds.
        self.ok(self.run_tool(root, "build", "--output", self.tmp / "site"))
        self.ok(self.run_tool(root, "configure", "--repository", "alice/other", "--name", "Again", "--url", NEW_URL))
        self.assertNotEqual(self.config(root)["id"], cfg["id"], "new UUIDs on every run")

    def test_fingerprint_option_and_clearing(self):
        root = self.make_root()
        self.write_config(root, publicKeyFingerprint=FP_A)
        self.ok(self.configure(root))
        self.assertIsNone(self.config(root)["publicKeyFingerprint"], "official fingerprint cleared")
        self.ok(self.configure(root, "alice/p", "P", NEW_URL, "--fingerprint", FP_B))
        self.assertEqual(self.config(root)["publicKeyFingerprint"], FP_B)

    def test_url_is_canonicalised(self):
        root = self.make_root()
        self.ok(self.configure(root, "alice/p", "P", "https://Alice.GitHub.io:443/p/"))
        self.assertEqual(self.config(root)["repositoryURL"], "https://alice.github.io/p/repository.json")

    def test_invalid_input_changes_nothing(self):
        bad = [
            ("alice", "N", NEW_URL, []), ("alice/", "N", NEW_URL, []), ("a/b/c", "N", NEW_URL, []),
            ("al ice/p", "N", NEW_URL, []), ("-alice/p", "N", NEW_URL, []), ("alice/..", "N", NEW_URL, []),
            ("alice/p", "", NEW_URL, []), ("alice/p", "x" * 81, NEW_URL, []), ("alice/p", "bad\nname", NEW_URL, []),
            ("alice/p", "N", "http://alice.github.io/p/repository.json", []),
            ("alice/p", "N", "https://user@alice.github.io/p/repository.json", []),
            ("alice/p", "N", "https://alice.github.io/p/repository.json?x=1", []),
            ("alice/p", "N", "https://alice.github.io/p/%2e/repository.json", []),
            ("alice/p", "N", "https://alice.github.io/../repository.json", []),
            ("alice/p", "N", "https://127.0.0.1/repository.json", []),
            ("alice/p", "N", "https://alice.github.io/p/repository.json#f", []),
            ("alice/p", "N", NEW_URL, ["--fingerprint", "xyz"]),
            ("alice/p", "N", NEW_URL, ["--fingerprint", FP_A.upper()]),
            ("alice/p", "N", NEW_URL, ["--fingerprint", FP_A[:-1]]),
            ("alice/p", "N", OFFICIAL_URL, []),
            ("alice/p", "N", OFFICIAL_URL.upper().replace("HTTPS", "https"), []),
            ("alice/p", "N", "https://qtmleap.github.io/Interceptor-Plugins/", []),
            ("qtmleap/Interceptor-Plugins", "N", NEW_URL, []),
            ("QTMLEAP/interceptor-plugins", "N", NEW_URL, []),
        ]
        for i, (repo, name, url, extra) in enumerate(bad):
            with self.subTest(repo=repo, name=name[:12], url=url, extra=extra):
                root = self.make_root(f"r{i}")
                before = tree_digest(root)
                self.fails(self.configure(root, repo, name, url, *extra))
                self.assertEqual(before, tree_digest(root))

    def test_reserved_fingerprint_is_refused(self):
        root = self.make_root()
        self.update_reserved(root, fingerprints=[FP_A])
        before = tree_digest(root)
        self.fails(self.configure(root, "alice/p", "P", NEW_URL, "--fingerprint", FP_A))
        self.assertEqual(before, tree_digest(root))

    def test_missing_or_duplicate_arguments(self):
        root = self.make_root()
        before = tree_digest(root)
        self.fails(self.run_tool(root, "configure", "--repository", "alice/p", "--name", "N"))
        self.fails(self.run_tool(root, "configure", "--repository", "alice/p", "--repository", "alice/q", "--name", "N", "--url", NEW_URL))
        self.fails(self.run_tool(root, "configure", "--repository", "alice/p", "--name", "N", "--url", NEW_URL, "--bogus", "1"))
        self.fails(self.run_tool(root, "configure", "--repository", "alice/p", "--name", "N", "--url", NEW_URL, "--fingerprint"))
        self.assertEqual(before, tree_digest(root))

    def test_malformed_existing_files_change_nothing(self):
        def bad_config(r): (r / "repository-config.json").write_text("{nope")
        def extra_key(r): self.write_config(r, extra=1)
        def dup_key(r): (r / "repository-config.json").write_text('{"schemaVersion":1,"schemaVersion":1}')
        def missing_pin(r):
            c = self.config(r); del c["upstreamRevision"]; (r / "repository-config.json").write_text(json.dumps(c))
        def bad_pin(r): self.write_config(r, upstreamRevision="main")
        def malformed_manifest(r): (r / "manifests" / "request-summary.json").write_text("[]")
        def bad_reserved(r): self.reserved_path(r).write_text('{"schemaVersion":2}')
        def missing_reserved(r): self.reserved_path(r).unlink()
        def symlinked_config(r):
            real = r / "real.json"; (r / "repository-config.json").rename(real); os.symlink(real, r / "repository-config.json")
        def symlinked_manifest(r):
            p = r / "manifests" / "request-summary.json"; real = r / "real-manifest.json"; p.rename(real); os.symlink(real, p)
        for i, mutate in enumerate([bad_config, extra_key, dup_key, missing_pin, bad_pin, malformed_manifest,
                                    bad_reserved, missing_reserved, symlinked_config, symlinked_manifest]):
            with self.subTest(mutate.__name__):
                root = self.make_root(f"m{i}")
                mutate(root)
                before = tree_digest(root)
                self.fails(self.configure(root))
                self.assertEqual(before, tree_digest(root))

    def test_failure_while_writing_leaves_everything_unchanged(self):
        root = self.make_root()
        before = tree_digest(root)
        os.chmod(root / "manifests", 0o500)
        try:
            self.fails(self.configure(root))
        finally:
            os.chmod(root / "manifests", 0o700)
        self.assertEqual(before, tree_digest(root))

    def test_refuses_checkout_whose_origin_is_official(self):
        for url in ("https://github.com/qtmleap/Interceptor-Plugins.git", "git@github.com:qtmleap/Interceptor-Plugins.git",
                    "https://github.com/QTMLEAP/interceptor-plugins", "ssh://git@github.com/qtmleap/Interceptor-Plugins/"):
            with self.subTest(url):
                root = self.make_root()
                git(root, "init", "-q"); git(root, "remote", "add", "origin", url)
                before = tree_digest(root)
                self.fails(self.configure(root))
                self.assertEqual(before, tree_digest(root))

    def test_origin_via_insteadof_and_pushurl_is_resolved(self):
        root = self.make_root()
        git(root, "init", "-q"); git(root, "remote", "add", "origin", "gh:foo/bar")
        git(root, "config", "url.https://github.com/qtmleap/Interceptor-Plugins.git.insteadOf", "gh:foo/bar")
        self.fails(self.configure(root))
        root2 = self.make_root("push")
        git(root2, "init", "-q"); git(root2, "remote", "add", "origin", "https://github.com/alice/my-plugins.git")
        git(root2, "remote", "set-url", "--push", "origin", "https://github.com/qtmleap/Interceptor-Plugins.git")
        self.fails(self.configure(root2))

    def test_allows_template_checkout_with_own_origin(self):
        root = self.make_root()
        git(root, "init", "-q"); git(root, "remote", "add", "origin", "https://github.com/alice/my-plugins.git")
        self.ok(self.configure(root))
        self.assertEqual(self.config(root)["githubRepository"], "alice/my-plugins")

    def test_allows_checkout_without_origin(self):
        root = self.make_root()
        git(root, "init", "-q")
        self.ok(self.configure(root))


if __name__ == "__main__":
    unittest.main()
