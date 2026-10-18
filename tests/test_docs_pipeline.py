"""Composition preservation/refusal and documentation metadata derivation, through the real CLIs."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from helpers import Case, REPO


def tree_digest(root):
    """Names, kinds and link targets only; never opens special files."""
    entries = []
    for dirpath, dirs, files in os.walk(root):
        for name in dirs + files:
            path = os.path.join(dirpath, name)
            info = os.lstat(path)
            entries.append((os.path.relpath(path, root), info.st_mode, info.st_size))
    return sorted(entries)

FEED_FILES = {"repository.json": b'{"signed":"envelope"}', ".nojekyll": b"",
              "plugins/a.json": b'{"a":1}\n', "plugins/b.json": b"\x00\xff exact bytes"}


def digests(root):
    out = {}
    for dirpath, _, names in os.walk(root):
        for name in names:
            path = os.path.join(dirpath, name)
            out[os.path.relpath(path, root).replace(os.sep, "/")] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return out


class ComposeTests(Case):
    def tool(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(REPO / "tools/compose_pages.py"), *map(str, args)],
                              capture_output=True, text=True, timeout=60, env=env)

    def tree(self, name, files):
        root = self.tmp / name
        shutil.rmtree(root, ignore_errors=True)
        for rel, data in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        root.mkdir(exist_ok=True)
        return root

    def inputs(self, docs=None, feed=None):
        feed_root = self.tree("feed", FEED_FILES if feed is None else feed)
        docs_root = self.tree("docs", {"index.html": b"<html>", "en/index.html": b"<html>en", "assets/app.js": b"1"}
                              if docs is None else docs)
        return feed_root, docs_root

    def refused(self, feed, docs, message=None):
        out = self.tmp / "pages"
        before = (tree_digest(feed), tree_digest(docs))
        proc = self.tool("--feed", feed, "--docs", docs, "--output", out)
        self.fails(proc)
        if message:
            self.assertIn(message, proc.stderr)
        self.assertFalse(out.exists(), "a refusal must not publish a partial tree")
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.startswith(".pages")], [])
        self.assertEqual(before, (tree_digest(feed), tree_digest(docs)))

    def test_preserves_every_feed_byte_and_adds_documentation(self):
        feed, docs = self.inputs()
        out = self.tmp / "pages"
        self.ok(self.tool("--feed", feed, "--docs", docs, "--output", out))
        result = digests(out)
        for rel, data in FEED_FILES.items():
            self.assertEqual(result[rel], hashlib.sha256(data).hexdigest(), rel)
        self.assertEqual(set(result), set(FEED_FILES) | {"index.html", "en/index.html", "assets/app.js"})
        self.assertEqual(digests(feed), {k: hashlib.sha256(v).hexdigest() for k, v in FEED_FILES.items()})

    def test_accepts_an_existing_empty_output_directory(self):
        feed, docs = self.inputs()
        out = self.tmp / "pages"
        out.mkdir()
        self.ok(self.tool("--feed", feed, "--docs", docs, "--output", out))
        self.assertTrue((out / "plugins/a.json").is_file())

    def test_refuses_a_non_empty_output(self):
        feed, docs = self.inputs()
        out = self.tmp / "pages"
        out.mkdir()
        (out / "stale").write_text("x")
        self.fails(self.tool("--feed", feed, "--docs", docs, "--output", out))
        self.assertEqual([p.name for p in out.iterdir()], ["stale"])

    def test_refuses_documentation_that_collides_with_the_feed(self):
        for rel in ("repository.json", ".nojekyll", "plugins/extra.json", "plugins", "Repository.JSON", "PLUGINS/x.json"):
            with self.subTest(rel=rel):
                docs = {"index.html": b"x", rel: b"docs"}
                feed, docs_root = self.inputs(docs=docs)
                self.refused(feed, docs_root)

    def test_refuses_unsafe_documentation_entries(self):
        cases = {
            "hidden": lambda d: (d / ".secret").write_text("x"),
            "hidden-directory": lambda d: ((d / ".git").mkdir(), (d / ".git/config").write_text("x")),
            "symlink": lambda d: (d / "link.html").symlink_to("index.html"),
            "dangling": lambda d: (d / "link.html").symlink_to("/nonexistent"),
            "hardlink": lambda d: os.link(d / "index.html", d / "again.html"),
            "fifo": lambda d: os.mkfifo(d / "pipe"),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                feed, docs = self.inputs()
                mutate(docs)
                self.refused(feed, docs)

    def test_refuses_casefold_and_compatibility_duplicates_inside_documentation(self):
        feed, docs = self.inputs(docs={"index.html": b"x", "Ｇuide.html": b"1", "guide.html": b"2"})
        self.refused(feed, docs)

    def test_refuses_unsafe_feed_entries_and_missing_pieces(self):
        feed, docs = self.inputs()
        (feed / "plugins/link.json").symlink_to("a.json")
        self.refused(feed, docs)
        feed, docs = self.inputs(feed={"repository.json": b"x", ".nojekyll": b""})
        self.refused(feed, docs)
        feed, docs = self.inputs(feed={"plugins/a.json": b"{}", ".nojekyll": b""})
        self.refused(feed, docs)

    def test_refuses_documentation_without_a_home_page(self):
        feed, docs = self.inputs(docs={"en/index.html": b"x"})
        self.refused(feed, docs)

    def test_refuses_oversized_documentation_files(self):
        feed, docs = self.inputs()
        with open(docs / "huge.bin", "wb") as handle:
            handle.truncate(26 * 1024 * 1024)
        self.refused(feed, docs)

    def test_refuses_output_overlapping_inputs(self):
        feed, docs = self.inputs()
        for out in (feed, docs, docs / "nested", feed / "plugins"):
            proc = self.tool("--feed", feed, "--docs", docs, "--output", out)
            self.fails(proc)
        self.assertEqual(digests(feed), {k: hashlib.sha256(v).hexdigest() for k, v in FEED_FILES.items()})

    def test_refuses_symlinked_inputs_and_output(self):
        feed, docs = self.inputs()
        alias = self.tmp / "docs-alias"
        alias.symlink_to(docs, target_is_directory=True)
        self.fails(self.tool("--feed", feed, "--docs", alias, "--output", self.tmp / "pages"))
        target = self.tmp / "target"
        target.mkdir()
        (self.tmp / "pages").symlink_to(target, target_is_directory=True)
        self.fails(self.tool("--feed", feed, "--docs", docs, "--output", self.tmp / "pages"))
        self.assertEqual(list(target.iterdir()), [])


class ContextTests(Case):
    def context(self, root, name="build/docs-context.json"):
        proc = self.run_tool(root, "docs_context", "--output", root / name)
        return proc, root / name

    def prepared(self, **config):
        root = self.make_root()
        (root / ".bun-version").write_text("1.3.6\n")
        if config:
            self.write_config(root, **config)
        return root

    def test_official_context_and_base(self):
        root = self.prepared(publicKeyFingerprint="c" * 64)
        proc, path = self.context(root)
        self.ok(proc)
        data = json.loads(path.read_text())
        self.assertEqual(data["base"], "/Interceptor-Plugins/")
        self.assertEqual(data["repositoryURL"], self.config(root)["repositoryURL"])
        self.assertEqual(data["githubRepository"], "qtmleap/Interceptor-Plugins")
        self.assertEqual(data["fingerprint"], "c" * 64)
        self.assertEqual(data["bunVersion"], "1.3.6")

    def test_custom_repository_does_not_inherit_official_identity(self):
        root = self.prepared(githubRepository="someone/my-plugins", name="<b>{{ 1+1 }}</b> plugins",
                             repositoryURL="https://someone.example.com/plugins/repository.json")
        proc, path = self.context(root)
        self.ok(proc)
        data = json.loads(path.read_text())
        self.assertEqual(data["base"], "/plugins/")
        self.assertEqual(data["name"], "<b>{{ 1+1 }}</b> plugins", "raw value; escaping happens at render time")
        self.assertIsNone(data["fingerprint"])
        self.assertNotIn("qtmleap", path.read_text().lower())

    def test_root_hosted_feed_uses_root_base(self):
        root = self.prepared(repositoryURL="https://plugins.example.com/repository.json")
        proc, path = self.context(root)
        self.ok(proc)
        self.assertEqual(json.loads(path.read_text())["base"], "/")

    def test_refuses_invalid_config_and_outputs_outside_build(self):
        root = self.prepared()
        self.write_config(root, repositoryURL="http://insecure.example.com/repository.json")
        proc, path = self.context(root)
        self.fails(proc)
        self.assertFalse(path.exists())
        root = self.prepared()
        proc = self.run_tool(root, "docs_context", "--output", root / "context.json")
        self.fails(proc)
        proc = self.run_tool(root, "docs_context", "--output", root / "build/../context.json")
        self.fails(proc)
        (root / ".bun-version").write_text("latest\n")
        proc, _ = self.context(root)
        self.fails(proc)
