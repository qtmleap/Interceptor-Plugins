import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class BootstrapTests(unittest.TestCase):
    def test_old_swift_fails_before_fetch_or_cache_creation(self):
        with tempfile.TemporaryDirectory(prefix="interceptor-old-swift-") as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            shutil.copy(Path(__file__).resolve().parents[1] / "bootstrap.sh", root / "tools" / "bootstrap.sh")
            (root / "repository-config.json").write_text(json.dumps({"upstreamRevision": "50307c2af38be2524f988e3d1d8a950973d63fd5"}))
            binary = root / "bin"
            binary.mkdir()
            (binary / "swift").write_text("#!/bin/sh\nprintf '%s\\n' 'Apple Swift version 6.1.2'\n")
            (binary / "git").write_text("#!/bin/sh\nexit 97\n")
            for p in binary.iterdir():
                p.chmod(0o755)
            result = subprocess.run(["bash", str(root / "tools" / "bootstrap.sh")], env=dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"]), capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Swift 6.4", result.stderr)
            self.assertFalse((root / ".tools").exists())


if __name__ == "__main__":
    unittest.main()
