#!/usr/bin/env python3
"""python3 tools/check_docs.py --root ROOT --site DIRECTORY [--context FILE]

Read-only checks of the documentation sources and of the built VitePress site: locale parity, source
includes confined to the canonical sources, internal links and anchors, local assets, search indexes,
unresolved metadata tokens and unpublishable files. Standard library only; writes nothing.
"""
import html
import json
import os
import re
import stat
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

from repository_config import BASELINE_URLS, ToolError, load_json, parse_args, run_main

PAGES = ("index", "getting-started", "authoring", "api", "examples", "publishing", "devcontainer")
LOCALES = {"": "ja", "en": "en"}  # directory under website/ -> <html lang>
INCLUDE_ROOTS = ("src", "types", "manifests", "fixtures")
FORBIDDEN_SUFFIXES = (".md", ".py", ".sh", ".key", ".pem", ".ts", ".swift", ".lock")
SEARCH_LOCALES = ("root", "en")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
TOKEN = re.compile(r"%%[A-Z_]+%%|%25%25[A-Z_]+%25%25")
SNIPPET = re.compile(r"^\s*<<<\s*(\S+?)(?:\{[^}]*\})?(?:\s*\[[^\]]*\])?\s*$")
INCLUDE = re.compile(r"<!--\s*@include:\s*(.*?)\s*-->")
MAX_TEXT = 8 * 1024 * 1024


# ---------------------------------------------------------------- sources

def source_pages(website):
    """Locale directory -> set of page slugs, from the Markdown files that exist."""
    found = {}
    for directory in LOCALES:
        folder = website / directory if directory else website
        if not folder.is_dir():
            raise ToolError(f"missing documentation directory: {folder}")
        found[directory] = {p.stem for p in folder.iterdir() if p.is_file() and p.suffix == ".md"}
    return found


def check_locales(website):
    pages = source_pages(website)
    errors = []
    for directory, slugs in pages.items():
        label = directory or "root"
        for slug in sorted(set(PAGES) - slugs):
            errors.append(f"locale {label}: missing page {slug}")
        for slug in sorted(slugs - set(PAGES)):
            errors.append(f"locale {label}: unexpected page {slug}")
    return errors


def markdown_files(website):
    for path in sorted(website.rglob("*.md")):
        parts = path.relative_to(website).parts
        if parts[0] in (".vitepress", "node_modules"):
            continue
        yield path


def resolve_include(root, website, page, target):
    """The real file an include points at, or an error message."""
    target = re.sub(r"(?:#[\w-]+)?(?:\{[^}]*\})?$", "", target)
    base = website if target.startswith("@/") else page.parent
    candidate = Path(os.path.normpath(base / target[2:] if target.startswith("@/") else base / target))
    root = Path(os.path.realpath(root))
    for name in INCLUDE_ROOTS:
        allowed = root / name
        try:
            relative = candidate.relative_to(allowed)
        except ValueError:
            try:
                relative = Path(os.path.realpath(candidate)).relative_to(allowed)
            except ValueError:
                continue
        walk = allowed
        for part in relative.parts:
            walk = walk / part
            if os.path.islink(walk):
                return f"include crosses a symlink: {target}"
        try:
            info = os.lstat(candidate)
        except FileNotFoundError:
            return f"include does not exist: {target}"
        if not stat.S_ISREG(info.st_mode):
            return f"include is not a regular file: {target}"
        return None
    return f"include must be inside {', '.join(INCLUDE_ROOTS)}: {target}"


def check_includes(root, website):
    errors = []
    for page in markdown_files(website):
        in_fence = False
        for number, line in enumerate(page.read_text("utf-8").splitlines(), 1):
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
            # VitePress expands HTML includes before Markdown parsing, even inside fences.
            targets = []
            if not in_fence and line.lstrip().startswith("<<<"):
                match = SNIPPET.fullmatch(line)
                if match:
                    targets.append(match.group(1))
                else:
                    errors.append(f"{page.relative_to(website)}:{number}: unsupported include syntax")
            targets += INCLUDE.findall(line)
            for target in targets:
                problem = resolve_include(root, website, page, target)
                if problem:
                    errors.append(f"{page.relative_to(website)}:{number}: {problem}")
    return errors


# ---------------------------------------------------------------- built site

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links, self.assets, self.lang = set(), [], [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("name"):
            self.ids.add(a["name"])
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "a" and a.get("href") is not None:
            self.links.append(a["href"])
        elif tag == "link" and a.get("href"):
            self.assets.append(a["href"])
        elif tag in ("script", "img", "source", "video", "audio", "iframe") and a.get("src"):
            self.assets.append(a["src"])


def read_text(path):
    if path.stat().st_size > MAX_TEXT:
        raise ToolError(f"file too large to check: {path}")
    return path.read_text("utf-8", "replace")


class Site:
    def __init__(self, directory, base):
        self.directory = Path(directory)
        self.base = base
        self.files = {}
        self.pages = {}
        for dirpath, dirnames, names in os.walk(self.directory):
            for name in names + dirnames:
                path = Path(dirpath) / name
                if path.is_symlink():
                    raise ToolError(f"symlink in built site: {path.relative_to(self.directory)}")
            for name in names:
                path = Path(dirpath) / name
                self.files[path.relative_to(self.directory).as_posix()] = path

    def page(self, rel):
        if rel not in self.pages:
            parser = Page()
            parser.feed(read_text(self.files[rel]))
            self.pages[rel] = parser
        return self.pages[rel]

    def page_url(self, rel):
        url = self.base + rel
        if rel.endswith("index.html"):
            return url[: -len("index.html")]
        return url

    def locate(self, url_path):
        """Built file for an absolute URL path, or None."""
        if not url_path.startswith(self.base):
            return None
        rel = unquote(url_path[len(self.base):])
        if PurePosixPath(rel).is_absolute() or ".." in PurePosixPath(rel).parts:
            return None
        if rel == "" or rel.endswith("/"):
            candidates = [rel + "index.html"]
        else:
            candidates = [rel, rel + ".html", rel + "/index.html"]
        return next((c for c in candidates if c in self.files), None)


def check_links(site):
    errors = []
    for rel in sorted(site.files):
        if not rel.endswith(".html"):
            continue
        page = site.page(rel)
        url = site.page_url(rel)
        for kind, values in (("link", page.links), ("asset", page.assets)):
            for value in values:
                if not value or value.startswith("//") or SCHEME.match(value):
                    continue
                joined = urlsplit(urljoin(url, value))
                if not joined.path.startswith(site.base):
                    errors.append(f"{rel}: {kind} outside the site base: {value}")
                    continue
                target = site.locate(joined.path)
                if target is None:
                    errors.append(f"{rel}: broken {kind}: {value}")
                    continue
                if kind == "link" and joined.fragment and target.endswith(".html"):
                    if unquote(joined.fragment) not in site.page(target).ids:
                        errors.append(f"{rel}: missing anchor: {value}")
    return errors


def check_locale_pages(site):
    errors = []
    for directory, lang in LOCALES.items():
        for slug in PAGES:
            rel = (directory + "/" if directory else "") + slug + ".html"
            if rel not in site.files:
                errors.append(f"built site is missing {rel}")
            elif site.page(rel).lang != lang:
                errors.append(f"{rel}: html lang is {site.page(rel).lang!r}, expected {lang!r}")
    if "404.html" not in site.files:
        errors.append("built site is missing 404.html")
    return errors


def check_search(site):
    errors = []
    for locale in SEARCH_LOCALES:
        matches = [rel for rel in site.files if re.search(rf"/@localSearchIndex{locale}\.[^/]*\.js$", "/" + rel)]
        if not matches:
            errors.append(f"missing local search index for {locale}")
        elif any(site.files[m].stat().st_size < 2 for m in matches):
            errors.append(f"empty local search index for {locale}")
    return errors


def check_publishable(site):
    errors = []
    for rel in sorted(site.files):
        parts = rel.split("/")
        if any(p.startswith(".") for p in parts):
            errors.append(f"hidden file in built site: {rel}")
        elif rel.lower().endswith(FORBIDDEN_SUFFIXES) or "superpowers" in rel:
            errors.append(f"unpublishable file in built site: {rel}")
        elif parts[0].lower() in ("repository.json", "plugins"):
            errors.append(f"built site collides with the feed: {rel}")
    return errors


def check_content(site, context, reserved_fingerprints):
    errors = []
    name = context["name"] if context else None
    unsafe = bool(name) and (name != html.escape(name) or "{{" in name or "}}" in name)
    foreign = []
    if context and context["repositoryURL"] not in BASELINE_URLS:
        foreign = [url.rsplit("/", 1)[0] for url in BASELINE_URLS] + list(reserved_fingerprints)
    for rel, path in sorted(site.files.items()):
        if not rel.endswith((".html", ".js", ".json", ".xml", ".txt")):
            continue
        text = read_text(path)
        if TOKEN.search(text):
            errors.append(f"{rel}: unresolved metadata token")
        # Literal names in serialized JS are data; HTML text/attributes must be escaped.
        markup = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", text, flags=re.I | re.S) if rel.endswith(".html") else ""
        if unsafe and name in markup:
            errors.append(f"{rel}: display name appears unescaped")
        for value in foreign:
            if value in text:
                errors.append(f"{rel}: contains the official identity {value[:48]}")
    return errors


def load_context(path):
    context = load_json(path, "documentation context")
    for key in ("name", "repositoryURL", "base"):
        if not isinstance(context.get(key), str):
            raise ToolError(f"documentation context: missing {key}")
    if not context["base"].startswith("/") or not context["base"].endswith("/"):
        raise ToolError("documentation context: invalid base")
    return context


def run_checks(root, site_dir, context):
    root = Path(root)
    website = root / "website"
    errors = check_locales(website) + check_includes(root, website)
    site = Site(site_dir, context["base"] if context else "/")
    reserved = []
    reserved_path = root / "tools" / "reserved.json"
    if reserved_path.is_file():
        reserved = [f for f in json.loads(reserved_path.read_text("utf-8")).get("fingerprints", []) if isinstance(f, str)]
    errors += (check_locale_pages(site) + check_links(site) + check_search(site) + check_publishable(site)
               + check_content(site, context, reserved))
    return errors


def main(argv):
    options = parse_args(argv, ("--root", "--site", "--context"), flags=("--context",))
    root = Path(options["--root"])
    context_path = Path(options.get("--context") or root / "build" / "docs-context.json")
    context = load_context(context_path)
    errors = run_checks(root, options["--site"], context)
    if errors:
        for line in errors[:100]:
            print(line)
        raise ToolError(f"{len(errors)} documentation problem(s)")
    print("Documentation checks passed.")


if __name__ == "__main__":
    run_main(main)
