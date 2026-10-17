"""Independent authoring fixtures for tool tests; never depend on a publisher's identity or scripts."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OFFICIAL_REPOSITORY = "qtmleap/Interceptor-Plugins"
OFFICIAL_REPOSITORY_ID = "90A213C0-9D3C-47F5-ABB8-C15C7472E2AD"
OFFICIAL_PLUGIN_IDS = ["76532D8C-608A-4EA3-AC16-755BABF2AB7E", "5B478646-4A70-4EF1-B04B-6CB63450E5A4"]
OFFICIAL_URL = "https://qtmleap.github.io/Interceptor-Plugins/repository.json"
UPSTREAM = "50307c2af38be2524f988e3d1d8a950973d63fd5"
FP_A = "a" * 64
FP_B = "b" * 64


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="plugins-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make_root(self, name="root"):
        """Known inputs for the real CLIs, independent of template configuration and user edits."""
        root = self.tmp / f"{name}-{len(list(self.tmp.iterdir()))}"
        root.mkdir()
        config = {"schemaVersion": 1, "id": OFFICIAL_REPOSITORY_ID, "name": "Tool fixture",
                  "githubRepository": OFFICIAL_REPOSITORY, "repositoryURL": OFFICIAL_URL,
                  "publicKeyFingerprint": None, "upstreamRevision": UPSTREAM}
        (root / "repository-config.json").write_text(json.dumps(config))
        for d in ("scripts", "manifests", "fixtures"):
            (root / d).mkdir()
        for index, (name, hook, phase) in enumerate((("request-summary", "onRequest", "request.completed"),
                                                    ("server-error-filter", "onResponse", "response.completed"))):
            manifest = {"schemaVersion": 1, "id": OFFICIAL_PLUGIN_IDS[index], "name": name, "version": "1.0.0",
                        "subscriptions": [{"phase": phase, "match": {"hosts": ["example.com"]}}],
                        "read": {"metadata": ["host"], "headers": [], "queryKeys": [], "body": {"mode": "none"}},
                        "endpointBindings": ["preview"], "settings": {}}
            (root / "manifests" / (name + ".json")).write_text(json.dumps(manifest))
            (root / "scripts" / (name + ".js")).write_text("function " + hook + "(event, config) { return { actions: [] }; }\n")
        (root / "fixtures" / "cases.json").write_text("[]\n")
        (root / "tools").mkdir()
        for f in (REPO / "tools").iterdir():
            if f.is_file() and (f.suffix == ".py" or f.name == "reserved.json"):
                shutil.copy(f, root / "tools" / f.name)
        self.update_reserved(root, ids=[OFFICIAL_REPOSITORY_ID] + OFFICIAL_PLUGIN_IDS, urls=[OFFICIAL_URL], fingerprints=[])
        return root

    def run_tool(self, root, tool, *args, with_root=True):
        cmd = [sys.executable, str(root / "tools" / f"{tool}.py")]
        if with_root:
            cmd += ["--root", str(root)]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run(cmd + [str(a) for a in args], capture_output=True, text=True, timeout=60, env=env)
        return proc

    def ok(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

    def fails(self, proc):
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertTrue(proc.stderr.strip(), "failure must explain itself on stderr")

    def config(self, root):
        return json.loads((root / "repository-config.json").read_text("utf-8"))

    def write_config(self, root, **changes):
        cfg = self.config(root)
        cfg.update(changes)
        (root / "repository-config.json").write_text(json.dumps(cfg, indent=2) + "\n", "utf-8")

    def reserved_path(self, root):
        return root / "tools" / "reserved.json"

    def update_reserved(self, root, **changes):
        data = json.loads(self.reserved_path(root).read_text("utf-8"))
        data.update(changes)
        self.reserved_path(root).write_text(json.dumps(data, indent=2) + "\n", "utf-8")

    def manifest_ids(self, root):
        return sorted(json.loads(p.read_text("utf-8"))["id"] for p in (root / "manifests").glob("*.json"))


def tree_digest(root):
    """Digest of every file path + bytes (symlinks recorded as such) for no-partial-change assertions."""
    h = hashlib.sha256()
    for dirpath, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files + [d for d in dirs if os.path.islink(os.path.join(dirpath, d))]):
            path = os.path.join(dirpath, name)
            h.update(os.path.relpath(path, root).encode() + b"\0")
            h.update(os.readlink(path).encode() if os.path.islink(path) else Path(path).read_bytes())
        for d in dirs:
            h.update(b"D" + os.path.relpath(os.path.join(dirpath, d), root).encode() + b"\0")
    return h.hexdigest()
