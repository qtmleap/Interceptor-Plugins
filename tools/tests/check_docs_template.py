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
        self.images, self.text, self.hero_text, self.icons = [], [], [], []
        self.in_heading = False

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.images.append(dict(attrs))
        if tag == "h1":
            self.in_heading = True
        if tag == "link" and "icon" in dict(attrs).get("rel", "").split():
            self.icons.append(dict(attrs))

    def handle_endtag(self, tag):
        if tag == "h1":
            self.in_heading = False

    def handle_data(self, text):
        self.text.append(text)
        if self.in_heading:
            self.hero_text.append(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    name = 'Template </script><img src=x onerror=alert(1)><!--{{7*7}} & "tea"'
    with tempfile.TemporaryDirectory(prefix="interceptor-docs-template-") as directory:
        root = Path(directory)
        for folder in ("tools", "src", "types", "manifests", "fixtures", "website", "docs/diagrams"):
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
        for file in ("index.html", "en/index.html", "authoring.html", "en/authoring.html",
                     "api.html", "en/api.html", "examples.html", "en/examples.html",
                     "getting-started.html", "en/getting-started.html"):
            html = (root / "build/docs" / file).read_text()
            page = Page()
            page.feed(html)
            assert name in "".join(page.text), f"display name was not rendered literally: {file}"
            locale = "en" if file.startswith("en/") else "ja"
            home = file in ("index.html", "en/index.html")
            icon = "/my-plugins/images/interceptor.png"
            if home:
                assert name in "".join(page.hero_text), f"custom hero name was not rendered literally: {file}"
            assert [entry.get("href") for entry in page.icons] == [icon], f"incorrect favicon base: {file}"
            expected = {icon} | (set() if home else
                        {f"/my-plugins/diagrams/plugin-hooks-{locale}-{theme}.svg" for theme in ("light", "dark")})
            if home:
                expected |= {f"/my-plugins/icons/{name}.svg" for name in ("filter", "json", "terminal", "package")}
            assert {image.get("src") for image in page.images} == expected, f"unexpected image or injected image: {file}"
            assert len(page.images) == (6 if home else 3), f"unexpected image count: {file}"
            assert all(not any(key.startswith("on") for key in image) for image in page.images)
            assert "/my-plugins/" in html
            assert "qtmleap.github.io/Interceptor-Plugins" not in html
        print("Configured documentation template and literal metadata checks passed.")


if __name__ == "__main__":
    main()
