import json
import os
import unittest
from pathlib import Path

from helpers import Case, OFFICIAL_PLUGIN_IDS, tree_digest


class BuildTests(Case):
    def build(self, root, out):
        return self.run_tool(root, "build", "--output", out)

    def test_builds_exact_artifacts(self):
        root = self.make_root()
        out = self.tmp / "site"
        self.ok(self.build(root, out))
        listing = sorted(str(p.relative_to(out)) for p in out.rglob("*"))
        self.assertEqual(listing, [".nojekyll", "plugins", "plugins/request-summary.json", "plugins/server-error-filter.json"])
        self.assertEqual((out / ".nojekyll").read_bytes(), b"")
        for name in ("request-summary", "server-error-filter"):
            raw = (out / "plugins" / f"{name}.json").read_bytes()
            manifest = json.loads((root / "manifests" / f"{name}.json").read_text("utf-8"))
            source = (root / "scripts" / f"{name}.js").read_text("utf-8")
            self.assertEqual(json.loads(raw), {"manifest": manifest, "source": source})
            expected = json.dumps({"manifest": manifest, "source": source}, sort_keys=True,
                                  separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            self.assertEqual(raw, expected)
            self.assertLessEqual(len(raw), 262144)

    def test_deterministic_across_runs_and_roots(self):
        a, b = self.make_root("a"), self.make_root("b")
        self.ok(self.build(a, self.tmp / "o1"))
        self.ok(self.build(b, self.tmp / "o2"))
        self.assertEqual(tree_digest(self.tmp / "o1"), tree_digest(self.tmp / "o2"))

    def test_rejects_without_partial_output(self):
        def drop_manifest(r): (r / "manifests" / "request-summary.json").unlink()
        def drop_script(r): (r / "scripts" / "server-error-filter.js").unlink()
        def symlink_script(r):
            p = r / "scripts" / "request-summary.js"; p.unlink(); os.symlink(r / "fixtures" / "cases.json", p)
        def symlink_manifest(r):
            p = r / "manifests" / "request-summary.json"; real = r / "elsewhere.json"
            p.rename(real); os.symlink(real, p)
        def symlink_dir(r):
            real = r / "scripts_real"; (r / "scripts").rename(real); os.symlink(real, r / "scripts")
        def duplicate_id(r):
            src = json.loads((r / "manifests" / "request-summary.json").read_text())
            other = r / "manifests" / "server-error-filter.json"
            m = json.loads(other.read_text()); m["id"] = src["id"].lower(); other.write_text(json.dumps(m))
        def bad_name_upper(r):
            (r / "scripts" / "Bad.js").write_text("x"); (r / "manifests" / "Bad.json").write_text("{}")
        def bad_name_space(r):
            (r / "scripts" / "a b.js").write_text("x"); (r / "manifests" / "a b.json").write_text("{}")
        def bad_name_dot(r):
            (r / "scripts" / "..x.js").write_text("x"); (r / "manifests" / "..x.json").write_text("{}")
        def stray(r): (r / "scripts" / "notes.txt").write_text("x")
        def stray_dir(r): (r / "manifests" / "sub").mkdir()
        def malformed(r): (r / "manifests" / "request-summary.json").write_text("{nope")
        def dup_key(r):
            (r / "manifests" / "request-summary.json").write_text('{"id":"x","id":"y"}')
        def bad_manifest(r):
            m = json.loads((r / "manifests" / "request-summary.json").read_text()); m["version"] = "1.0"
            (r / "manifests" / "request-summary.json").write_text(json.dumps(m))
        def extra_key(r):
            m = json.loads((r / "manifests" / "request-summary.json").read_text()); m["extra"] = 1
            (r / "manifests" / "request-summary.json").write_text(json.dumps(m))
        def bad_utf8(r): (r / "scripts" / "request-summary.js").write_bytes(b"function onRequest(){}\xff")
        def crlf_nul(r): (r / "scripts" / "request-summary.js").write_bytes(b"x\x00y")
        def oversized(r): (r / "scripts" / "request-summary.js").write_text("//" + "a" * 140000)
        def empty(r):
            for p in list((r / "scripts").iterdir()) + list((r / "manifests").iterdir()): p.unlink()
        mutations = [drop_manifest, drop_script, symlink_script, symlink_manifest, symlink_dir, duplicate_id,
                     bad_name_upper, bad_name_space, bad_name_dot, stray, stray_dir, malformed, dup_key,
                     bad_manifest, extra_key, bad_utf8, crlf_nul, oversized, empty]
        for i, mutate in enumerate(mutations):
            with self.subTest(mutate.__name__):
                root = self.make_root(f"r{i}")
                mutate(root)
                out = self.tmp / f"out{i}"
                before = tree_digest(root)
                self.fails(self.build(root, out))
                self.assertFalse(out.exists(), "no partial output")
                self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.startswith(".")], [], "no stray temp")
                self.assertEqual(before, tree_digest(root))

    def test_existing_output_must_be_absent_or_empty(self):
        root = self.make_root()
        out = self.tmp / "busy"; out.mkdir(); (out / "keep.txt").write_text("keep")
        before = tree_digest(out)
        self.fails(self.build(root, out))
        self.assertEqual(before, tree_digest(out))
        empty = self.tmp / "empty"; empty.mkdir()
        self.ok(self.build(root, empty))
        self.assertTrue((empty / "plugins" / "request-summary.json").is_file())

    def test_output_inside_sources_or_symlink_refused(self):
        root = self.make_root()
        self.fails(self.build(root, root / "scripts" / "out"))
        self.fails(self.build(root, root))
        link = self.tmp / "link"; os.symlink(self.tmp, link)
        self.fails(self.build(root, link))

    def test_usage_errors(self):
        root = self.make_root()
        self.fails(self.run_tool(root, "build"))
        self.fails(self.run_tool(root, "build", "--output", self.tmp / "x", "--bogus", "1"))
        self.fails(self.run_tool(root, "build", "--output", self.tmp / "y", with_root=False))
        self.fails(self.run_tool(root, "build", "--root", self.tmp / "missing", "--output", self.tmp / "z", with_root=False))


if __name__ == "__main__":
    unittest.main()
