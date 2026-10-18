#!/usr/bin/env python3
"""python3 tools/docs_context.py --root ROOT --output FILE

Derive the documentation build context from the validated repository-config.json and .bun-version.
FILE must be a new or existing regular file inside ROOT/build; it is written atomically.
Standard library only; no keys or network.
"""
import json
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from repository_config import ToolError, load_config, parse_args, read_regular, run_main

BUN_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def derive(root):
    """Plain values only. Escaping for display happens where the value is rendered."""
    root = Path(root)
    config = load_config(root)
    bun = read_regular(root / ".bun-version", 64).decode("utf-8", "replace").strip()
    if not BUN_VERSION_RE.match(bun):
        raise ToolError(".bun-version: expected an exact version")
    parts = urlsplit(config["repositoryURL"])
    directory = parts.path.rsplit("/", 1)[0]  # canonical URLs always end in a feed file name
    base = directory.rstrip("/") + "/"
    return {
        "schemaVersion": 1,
        "name": config["name"],
        "repositoryURL": config["repositoryURL"],
        "githubRepository": config["githubRepository"],
        "fingerprint": config["publicKeyFingerprint"],
        "bunVersion": bun,
        "origin": f"{parts.scheme}://{parts.netloc}",
        "base": base,
    }


def checked_target(root, output):
    build = Path(os.path.realpath(Path(root) / "build"))
    if os.path.islink(output):
        raise ToolError("output must not be a symlink")
    target = Path(os.path.realpath(output))
    if build not in target.parents:
        raise ToolError("context must be written inside build/")
    if target.exists() and not target.is_file():
        raise ToolError("context output is not a regular file")
    return target


def write_context(root, output):
    context = derive(root)
    target = checked_target(root, output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.parent / f".{target.name}.{uuid.uuid4().hex}.tmp"
    try:
        temp.write_text(json.dumps(context, indent=2, ensure_ascii=False) + "\n", "utf-8")
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()
    return context


def main(argv):
    options = parse_args(argv, ("--root", "--output"))
    root = Path(options["--root"])
    if not root.is_dir():
        raise ToolError(f"root is not a directory: {root}")
    write_context(root, options["--output"])
    print(f"wrote documentation context {options['--output']}")


if __name__ == "__main__":
    run_main(main)
