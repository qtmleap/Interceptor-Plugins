#!/usr/bin/env python3
"""Check an independently configured template with the real tools and native driver."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--verifier", required=True)
    parser.add_argument("--publisher", required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="interceptor-template-") as directory:
        root = Path(directory)
        ignore = shutil.ignore_patterns(".build", ".swiftpm", "__pycache__", "*.pyc")
        for name in ("tools", "tests", "scripts", "manifests", "fixtures"):
            shutil.copytree(args.root / name, root / name, ignore=ignore)
        shutil.copy(args.root / "repository-config.json", root / "repository-config.json")

        def run(*command):
            subprocess.run([str(value) for value in command], cwd=root, check=True)

        run(sys.executable, "tools/configure.py", "--root", root, "--repository", "sample-owner/my-plugins", "--name", "Template smoke test", "--url", "https://sample-owner.github.io/my-plugins/repository.json", "--fingerprint", "a" * 64)
        run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
        run(sys.executable, "tools/guard.py", "--root", root, "--repository", "sample-owner/my-plugins", "--ref", "refs/heads/master")
        site = root / "site"
        run(sys.executable, "tools/build.py", "--root", root, "--output", site)
        run(args.verifier, "samples", root, site)
        config = json.loads((root / "repository-config.json").read_text())
        run(args.publisher, "publish", site, "--id", config["id"], "--name", config["name"], "--sequence", "1")
        run(args.verifier, "verify-local", root, site)
        print("Configured template checks passed.")


if __name__ == "__main__":
    main()
