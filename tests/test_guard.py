import json
import os
import unittest

from helpers import (Case, FP_A, FP_B, OFFICIAL_PLUGIN_IDS, OFFICIAL_REPOSITORY, OFFICIAL_REPOSITORY_ID, OFFICIAL_URL,
                     tree_digest)

REF = "refs/heads/master"
OTHER_URL = "https://alice.github.io/my-plugins/repository.json"
NEW_ID = "11111111-2222-4333-8444-555555555555"


class GuardTests(Case):
    def guard(self, root, repo=OFFICIAL_REPOSITORY, ref=REF):
        return self.run_tool(root, "guard", "--repository", repo, "--ref", ref)

    def official(self, **changes):
        root = self.make_root()
        self.write_config(root, publicKeyFingerprint=FP_A, **changes)
        self.update_reserved(root, fingerprints=[FP_A])
        return root

    def template(self, name="t", **changes):
        """A properly migrated template: fresh configuration, then a signing fingerprint."""
        root = self.make_root(name)
        self.ok(self.run_tool(root, "configure", "--repository", "alice/my-plugins", "--name", "Mine", "--url", OTHER_URL,
                              "--fingerprint", FP_B))
        if changes:
            self.write_config(root, **changes)
        return root

    def test_official_identity_with_fingerprint_passes(self):
        proc = self.guard(self.official())
        self.ok(proc)
        self.assertIn(FP_A, proc.stdout)
        self.assertIn(OFFICIAL_REPOSITORY, proc.stdout)

    def test_official_case_insensitive_repository(self):
        self.ok(self.guard(self.official(), "QTMLEAP/interceptor-plugins"))

    def test_official_unreserved_signer_is_rejected(self):
        root = self.official()
        self.write_config(root, publicKeyFingerprint=FP_B)
        self.fails(self.guard(root))

    def test_fingerprint_is_required(self):
        self.fails(self.guard(self.make_root()))
        for bad in ("", "xyz", FP_A.upper(), FP_A[:-1], FP_A + "a", 5, [FP_A]):
            with self.subTest(bad=bad):
                root = self.make_root()
                self.write_config(root, publicKeyFingerprint=bad)
                self.fails(self.guard(root))

    def test_ref_must_be_master_branch(self):
        root = self.official()
        for ref in ("refs/heads/dev", "refs/heads/main", "master", "refs/tags/master", "refs/pull/1/merge", "refs/heads/master2", "refs/heads/master/", ""):
            with self.subTest(ref=ref):
                self.fails(self.guard(root, ref=ref))

    def test_configured_repository_must_match_argument(self):
        self.fails(self.guard(self.official(), "alice/my-plugins"))
        self.fails(self.guard(self.template(), OFFICIAL_REPOSITORY))
        self.fails(self.guard(self.template(), "alice/other"))
        self.fails(self.guard(self.official(), "not-a-repository"))
        self.fails(self.guard(self.official(), ""))

    def test_migrated_template_passes(self):
        proc = self.guard(self.template(), "alice/my-plugins")
        self.ok(proc)
        self.assertIn(FP_B, proc.stdout)

    def test_template_cannot_reuse_official_identities(self):
        for field, value in (("id", OFFICIAL_REPOSITORY_ID), ("id", OFFICIAL_PLUGIN_IDS[0]),
                             ("id", OFFICIAL_REPOSITORY_ID.lower()), ("repositoryURL", OFFICIAL_URL),
                             ("repositoryURL", "https://QtmLeap.github.io/Interceptor-Plugins/repository.json"),
                             ("repositoryURL", "https://qtmleap.github.io/Interceptor-Plugins/"),
                             ("repositoryURL", "https://qtmleap.github.io:443/Interceptor-Plugins"),
                             ("publicKeyFingerprint", FP_A)):
            with self.subTest(field=field, value=value):
                root = self.template("a" + field + str(abs(hash(value)))[:6])
                if field == "publicKeyFingerprint":
                    self.update_reserved(root, fingerprints=[FP_A, "c" * 64])
                self.write_config(root, **{field: value})
                self.fails(self.guard(root, "alice/my-plugins"))

    def test_template_cannot_keep_official_plugin_ids(self):
        root = self.template()
        path = root / "manifests" / "request-summary.json"
        m = json.loads(path.read_text()); m["id"] = OFFICIAL_PLUGIN_IDS[0].lower(); path.write_text(json.dumps(m))
        self.fails(self.guard(root, "alice/my-plugins"))
        root2 = self.template("t2")
        path = root2 / "manifests" / "server-error-filter.json"
        m = json.loads(path.read_text()); m["id"] = OFFICIAL_REPOSITORY_ID; path.write_text(json.dumps(m))
        self.fails(self.guard(root2, "alice/my-plugins"))

    def test_unmigrated_official_copy_in_another_repository_fails(self):
        root = self.make_root()
        self.write_config(root, githubRepository="alice/my-plugins", publicKeyFingerprint=FP_B)
        self.fails(self.guard(root, "alice/my-plugins"))

    def test_retired_reserved_entries_survive_migration(self):
        old_id, old_url, old_fp = "AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE", "https://qtmleap.github.io/Interceptor-Plugins/recovery-20250101/repository.json", "d" * 64
        for field, value in (("id", old_id), ("repositoryURL", old_url), ("publicKeyFingerprint", old_fp)):
            with self.subTest(field=field):
                root = self.template("r" + field)
                reserved = json.loads(self.reserved_path(root).read_text())
                self.update_reserved(root, ids=reserved["ids"] + [old_id], urls=reserved["urls"] + [old_url],
                                     fingerprints=reserved["fingerprints"] + [old_fp])
                self.write_config(root, **{field: value})
                self.fails(self.guard(root, "alice/my-plugins"))

    def test_official_may_use_reserved_identity_but_not_foreign_url_or_id(self):
        root = self.official()
        self.write_config(root, repositoryURL="https://alice.github.io/my-plugins/repository.json")
        self.fails(self.guard(root))
        root = self.official()
        self.write_config(root, id=NEW_ID)
        self.fails(self.guard(root))

    def test_migrated_official_ids_pass_when_reserved(self):
        root = self.official()
        new_url = "https://qtmleap.github.io/Interceptor-Plugins/recovery-20261017/repository.json"
        reserved = json.loads(self.reserved_path(root).read_text())
        self.update_reserved(root, ids=reserved["ids"] + [NEW_ID], urls=reserved["urls"] + [new_url],
                             fingerprints=reserved["fingerprints"] + [FP_B])
        self.write_config(root, id=NEW_ID, repositoryURL=new_url, publicKeyFingerprint=FP_B)
        self.ok(self.guard(root))

    def test_malformed_inputs_fail_without_changes(self):
        def bad_config(r): (r / "repository-config.json").write_text("{")
        def extra(r): self.write_config(r, rogue=True)
        def schema(r): self.write_config(r, schemaVersion=2)
        def bad_id(r): self.write_config(r, id="nope")
        def bad_url(r): self.write_config(r, repositoryURL="http://qtmleap.github.io/Interceptor-Plugins/repository.json")
        def bad_repo(r): self.write_config(r, githubRepository="qtmleap")
        def bad_pin(r): self.write_config(r, upstreamRevision="abc")
        def bad_reserved(r): self.reserved_path(r).write_text("[]")
        def reserved_bad_ids(r): self.update_reserved(r, ids=["not-a-uuid"])
        def reserved_wrong_owner(r): self.update_reserved(r, officialRepository="x/y")
        def reserved_missing(r): self.reserved_path(r).unlink()
        def bad_manifest(r): (r / "manifests" / "request-summary.json").write_text("{")
        def manifest_symlink(r):
            p = r / "manifests" / "request-summary.json"; real = r / "m.json"; p.rename(real); os.symlink(real, p)
        def config_symlink(r):
            real = r / "c.json"; (r / "repository-config.json").rename(real); os.symlink(real, r / "repository-config.json")
        for i, mutate in enumerate([bad_config, extra, schema, bad_id, bad_url, bad_repo, bad_pin, bad_reserved,
                                    reserved_bad_ids, reserved_wrong_owner, reserved_missing, bad_manifest,
                                    manifest_symlink, config_symlink]):
            with self.subTest(mutate.__name__):
                root = self.official()
                self.tmp_clean = True
                mutate(root)
                before = tree_digest(root)
                self.fails(self.guard(root))
                self.assertEqual(before, tree_digest(root))

    def test_usage_errors(self):
        root = self.official()
        self.fails(self.run_tool(root, "guard"))
        self.fails(self.run_tool(root, "guard", "--repository", OFFICIAL_REPOSITORY))
        self.fails(self.run_tool(root, "guard", "--ref", REF))
        self.fails(self.run_tool(root, "guard", "--repository", OFFICIAL_REPOSITORY, "--ref", REF, "--extra", "1"))
        self.fails(self.run_tool(root, "guard", "--repository", OFFICIAL_REPOSITORY, "--ref", REF, with_root=False))


if __name__ == "__main__":
    unittest.main()
