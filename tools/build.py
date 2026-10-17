#!/usr/bin/env python3
"""python3 tools/build.py --root ROOT --output DIRECTORY

Writes plugins/NAME.json (deterministic {manifest, source} packages) and an empty .nojekyll.
No keys, publisher or network. The output directory must be absent or empty and is created atomically.
"""
import os
import shutil
import uuid
from pathlib import Path

from repository_config import ToolError, load_samples, package_bytes, parse_args, run_main


def checked_output(root, output):
    if os.path.islink(output):
        raise ToolError("output must not be a symlink")
    output = Path(os.path.realpath(output))
    root = Path(os.path.realpath(root))
    sources = [root] + [root / d for d in ("scripts", "manifests", "fixtures", "tools")]
    if output == root or root in output.parents and any(output == s or s in output.parents for s in sources[1:]):
        raise ToolError("output must not be inside the editable sources")
    if output in root.parents:
        raise ToolError("output must not contain the source root")
    if not output.parent.is_dir():
        raise ToolError(f"output parent does not exist: {output.parent}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ToolError("output must be absent or an empty directory")
    return output


def main(argv):
    options = parse_args(argv, ("--root", "--output"))
    root = Path(options["--root"])
    if not root.is_dir():
        raise ToolError(f"root is not a directory: {root}")
    output = checked_output(root, options["--output"])
    packages = {name: package_bytes(manifest, source) for name, manifest, source in load_samples(root)}

    temp = output.parent / f".{output.name}.{uuid.uuid4().hex}.tmp"
    try:
        (temp / "plugins").mkdir(parents=True)
        for name, data in packages.items():
            (temp / "plugins" / f"{name}.json").write_bytes(data)
        (temp / ".nojekyll").write_bytes(b"")
        os.replace(temp, output)
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    print(f"built {len(packages)} packages into {output}")


if __name__ == "__main__":
    run_main(main)
