#!/usr/bin/env python3
"""python3 tools/compose_pages.py --feed DIRECTORY --docs DIRECTORY --output DIRECTORY

Stage one GitHub Pages tree from the signed feed (build/site) and the built documentation.
Every feed file is copied byte for byte; documentation may only add files. Symlinks, hard links,
special files, unexpected hidden entries, case-insensitive collisions with the feed and unreasonable
sizes are refused. The output must be absent or empty and is created atomically. Standard library only;
no keys, network or documentation dependencies.
"""
import hashlib
import os
import shutil
import stat
import unicodedata
import uuid
from pathlib import Path

from repository_config import ToolError, parse_args, run_main

FEED_HIDDEN = (".nojekyll",)
FEED_RESERVED = ("repository.json", "plugins", ".nojekyll")
FEED_REQUIRED = ("repository.json", ".nojekyll")

FEED_LIMITS = {"max_files": 100, "max_file": 4 * 1024 * 1024, "max_total": 16 * 1024 * 1024}
DOCS_LIMITS = {"max_files": 5000, "max_file": 25 * 1024 * 1024, "max_total": 200 * 1024 * 1024}
MAX_DEPTH = 12
MAX_NAME = 255


def fold(path):
    """Comparison key for case-insensitive, normalization-insensitive file systems."""
    return unicodedata.normalize("NFKC", path).casefold()


def _check_name(name, where):
    if (not name or name in (".", "..") or len(name.encode("utf-8", "replace")) > MAX_NAME or "\\" in name or "/" in name
            or any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp", "Cs") for c in name)):
        raise ToolError(f"unsafe file name in {where}: {name!r}")


def scan_tree(root, *, hidden=(), skip=(), ignore=(), max_files, max_file, max_total, suffixes=None):
    """Regular files under root as a sorted list of (posix relative path, size).

    hidden: relative paths allowed to start with a dot. skip: top-level names left out entirely.
    ignore: regular file names (e.g. .DS_Store) silently left out. Everything else unusual is an error.
    """
    root = Path(root)
    try:
        info = os.lstat(root)
    except FileNotFoundError:
        raise ToolError(f"missing directory: {root}")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ToolError(f"not a real directory: {root}")
    files = []
    seen = {}
    total = 0

    def visit(directory, prefix, depth):
        nonlocal total
        if depth > MAX_DEPTH:
            raise ToolError(f"directory nesting is too deep: {prefix}")
        for name in sorted(os.listdir(directory)):
            rel = prefix + name
            _check_name(name, rel)
            if not prefix and name in skip:
                continue
            path = os.path.join(directory, name)
            info = os.lstat(path)
            if stat.S_ISREG(info.st_mode) and name in ignore:
                continue
            if name.startswith(".") and rel not in hidden:
                raise ToolError(f"unexpected hidden entry: {rel}")
            key = fold(rel)
            if key in seen:
                raise ToolError(f"names collide on a case-insensitive file system: {rel} and {seen[key]}")
            seen[key] = rel
            if stat.S_ISLNK(info.st_mode):
                raise ToolError(f"symlinks are not allowed: {rel}")
            if stat.S_ISDIR(info.st_mode):
                visit(path, rel + "/", depth + 1)
                continue
            if not stat.S_ISREG(info.st_mode):
                raise ToolError(f"special files are not allowed: {rel}")
            if info.st_nlink != 1:
                raise ToolError(f"hard links are not allowed: {rel}")
            if suffixes is not None and not rel.lower().endswith(suffixes):
                raise ToolError(f"unexpected file type: {rel}")
            if info.st_size > max_file:
                raise ToolError(f"file too large: {rel}")
            total += info.st_size
            if len(files) + 1 > max_files or total > max_total:
                raise ToolError(f"{root} is larger than the allowed bounds")
            files.append((rel, info.st_size))

    visit(str(root), "", 0)
    # A file and a directory sharing a name (after folding) is already caught through `seen`.
    return files


def read_file(root, rel, limit):
    """Bytes of a regular, single-link, non-symlink file, checked on the opened descriptor."""
    path = os.path.join(root, *rel.split("/"))
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode):
        raise ToolError(f"not a regular file: {rel}")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as handle:
        after = os.fstat(handle.fileno())
        if (not stat.S_ISREG(after.st_mode) or after.st_nlink != 1
                or (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)):
            raise ToolError(f"file changed while reading: {rel}")
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ToolError(f"file too large: {rel}")
    return data


def check_output(feed, docs, output):
    if os.path.islink(output):
        raise ToolError("output must not be a symlink")
    output = Path(os.path.realpath(output))
    feed, docs = Path(os.path.realpath(feed)), Path(os.path.realpath(docs))
    for source in (feed, docs):
        if output == source or source in output.parents or output in source.parents:
            raise ToolError("output must not overlap the feed or documentation")
    if not output.parent.is_dir():
        raise ToolError(f"output parent does not exist: {output.parent}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ToolError("output must be absent or an empty directory")
    return output


def plan(feed, docs):
    """(feed files, docs files) after every refusal rule, without writing anything."""
    feed_files = scan_tree(feed, hidden=FEED_HIDDEN, **FEED_LIMITS)
    docs_files = scan_tree(docs, **DOCS_LIMITS)
    feed_names = {path for path, _ in feed_files}
    for required in FEED_REQUIRED:
        if required not in feed_names:
            raise ToolError(f"feed is missing {required}")
    if not any(path.startswith("plugins/") for path in feed_names):
        raise ToolError("feed has no plugins")
    if "index.html" not in {path for path, _ in docs_files}:
        raise ToolError("documentation has no index.html")
    reserved = {fold(name) for name in FEED_RESERVED}
    feed_keys = {fold(path) for path in feed_names}
    feed_dirs = {fold("/".join(path.split("/")[:i])) for path in feed_names for i in range(1, len(path.split("/")))}
    for path, _ in docs_files:
        parts = path.split("/")
        if fold(parts[0]) in reserved:
            raise ToolError(f"documentation collides with the feed: {path}")
        key = fold(path)
        if key in feed_keys or key in feed_dirs:
            raise ToolError(f"documentation collides with the feed: {path}")
        for i in range(1, len(parts)):
            if fold("/".join(parts[:i])) in feed_keys:
                raise ToolError(f"documentation collides with the feed: {path}")
    return feed_files, docs_files


def compose(feed, docs, output):
    output = check_output(feed, docs, output)
    feed_files, docs_files = plan(feed, docs)
    staging = output.parent / f".{output.name}.{uuid.uuid4().hex}.tmp"
    try:
        staging.mkdir()
        copied = []
        for source, files, limits in ((feed, feed_files, FEED_LIMITS), (docs, docs_files, DOCS_LIMITS)):
            for rel, _ in files:
                data = read_file(source, rel, limits["max_file"])
                target = staging.joinpath(*rel.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "xb") as handle:
                    handle.write(data)
                os.chmod(target, 0o644)
                copied.append((source is feed, rel, hashlib.sha256(data).hexdigest()))
        for directory, _, _ in os.walk(staging):
            os.chmod(directory, 0o755)
        # Re-read the staged tree: the feed must be exactly its inputs, and nothing else may appear.
        expected = {rel: digest for _, rel, digest in copied}
        found = scan_tree(staging, hidden=FEED_HIDDEN, **DOCS_LIMITS)
        if {rel for rel, _ in found} != set(expected):
            raise ToolError("staged tree differs from the planned file set")
        for rel, _ in found:
            if hashlib.sha256(read_file(staging, rel, DOCS_LIMITS["max_file"])).hexdigest() != expected[rel]:
                raise ToolError(f"staged bytes differ: {rel}")
        if output.exists():
            output.rmdir()
        os.replace(staging, output)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return len(feed_files), len(docs_files)


def main(argv):
    options = parse_args(argv, ("--feed", "--docs", "--output"))
    feed_count, docs_count = compose(options["--feed"], options["--docs"], options["--output"])
    print(f"composed {feed_count} feed files and {docs_count} documentation files into {options['--output']}")


if __name__ == "__main__":
    run_main(main)
