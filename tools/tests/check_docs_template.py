#!/usr/bin/env python3
"""Build a configured docs copy without signing keys, Git writes or native release tools."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images, self.text = [], []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.images.append(dict(attrs))

    def handle_data(self, text):
        self.text.append(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    name = 'Template </script><img src=x onerror=alert(1)><!--{{7*7}} & "tea"'
    with tempfile.TemporaryDirectory(prefix="interceptor-docs-template-") as directory:
        root = Path(directory)
        for folder in ("tools", "src", "types", "manifests", "fixtures", "website"):
            shutil.copytree(args.root / folder, root / folder,
                            ignore=shutil.ignore_patterns(".build", ".swiftpm", "__pycache__", "*.pyc"))
        for file in ("repository-config.json", "package.json", "bun.lock", ".bun-version"):
            shutil.copyfile(args.root / file, root / file)

        def run(*command):
            subprocess.run([str(value) for value in command], cwd=root, check=True)

        run("bun", "install", "--frozen-lockfile", "--ignore-scripts")
        run(sys.executable, "tools/configure.py", "--root", root, "--repository", "sample-owner/my-plugins",
            "--name", name, "--url", "https://sample-owner.github.io/my-plugins/repository.json")
        run("bun", "run", "check:docs")
        context = json.loads((root / "build/docs-context.json").read_text())
        assert context["fingerprint"] is None and context["base"] == "/my-plugins/"
        for file in ("index.html", "en/index.html"):
            html = (root / "build/docs" / file).read_text()
            page = Page()
            page.feed(html)
            assert name in "".join(page.text), f"display name was not rendered literally: {file}"
            assert not page.images, f"display name injected an image: {file}"
            assert "/my-plugins/" in html
            assert "qtmleap.github.io/Interceptor-Plugins" not in html
        print("Configured documentation template and literal metadata checks passed.")


if __name__ == "__main__":
    main()
