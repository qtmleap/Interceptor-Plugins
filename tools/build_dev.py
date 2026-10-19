#!/usr/bin/env python3
"""python3 tools/build_dev.py --root ROOT

Runs the canonical tools/build.py into a staging directory, then replaces build/dev (packages in
build/dev/plugins/NAME.json) only if compilation and packaging succeeded. build/dev has a marker; a
non-empty unowned or symlinked output is refused and build/site is never touched.
The canonical build also regenerates build/scripts and build/manifests before packaging; those can
advance even if packaging fails. Use a real root path with no symlinked ancestors (including macOS
/tmp or /var aliases); resolve it first when needed.

Replacement is two renames (a non-empty directory cannot be renamed over another one), so build/dev is
briefly absent. The previous output is kept as a backup until the new one is in place, restored on
failure, and recovered by the next run if the process died in between.
"""
import fcntl
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from repository_config import ToolError, parse_args, run_main

MARKER = ".build-dev-owned"
MARKER_TEXT = b"interceptor-plugins build:dev output\n"


def owned(directory):
    marker = directory / MARKER
    return directory.is_dir() and not directory.is_symlink() and marker.is_file() and not marker.is_symlink() \
        and marker.stat().st_size == len(MARKER_TEXT) and marker.read_bytes() == MARKER_TEXT


def remove_owned(directory):
    if not owned(directory):
        raise ToolError(f"refusing to delete unowned directory: {directory}")
    shutil.rmtree(directory)


def recover(build, output):
    """Finish an interrupted replacement: restore an owned backup if output is gone, else drop old backups."""
    for backup in sorted(build.glob(".dev.backup.*")):
        if not owned(backup):
            continue
        if output.exists() or output.is_symlink():
            remove_owned(backup)
        else:
            os.rename(backup, output)


def check_output(output):
    if output.is_symlink():
        raise ToolError("output must not be a symlink")
    if output.exists() and not owned(output):
        if not output.is_dir() or any(output.iterdir()):
            raise ToolError("build/dev exists but is not owned by build:dev (no marker) or not empty")


def replace(build, stage, output):
    backup = None
    try:
        if output.exists():
            if any(output.iterdir()):
                backup = build / f".dev.backup.{uuid.uuid4().hex}"
                os.rename(output, backup)
            else:
                output.rmdir()
        os.rename(stage, output)
    except BaseException:
        if backup and backup.exists() and not output.exists():
            os.rename(backup, output)
        raise
    if backup:
        try:
            remove_owned(backup)
        except (OSError, ToolError) as error:
            raise ToolError(f"new packages published to {output}; backup cleanup failed at {backup}: {error}") from error


def main(argv):
    options = parse_args(argv, ("--root",))
    root = Path(options["--root"]).absolute()
    for path in (root, *root.parents):
        if path.is_symlink():
            raise ToolError(f"symlinked root path: {path}; use a resolved real path")
    if not root.is_dir():
        raise ToolError(f"root must be a real directory: {root}")
    root = root.resolve()
    build = root / "build"
    if build.is_symlink() or (build.exists() and not build.is_dir()):
        raise ToolError("build must be a real directory")
    build.mkdir(exist_ok=True)
    output = build / "dev"
    lock_path = build / ".dev.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ToolError("another build:dev is running in this checkout")
        check_output(output)
        recover(build, output)
        check_output(output)
        stage = build / f".dev.stage.{uuid.uuid4().hex}"
        try:
            proc = subprocess.run([sys.executable, str(root / "tools/build.py"), "--root", str(root), "--output", str(stage)],
                                  capture_output=True, text=True)
            if proc.returncode:
                raise ToolError("build failed; build/dev unchanged:\n" + (proc.stderr or proc.stdout))
            (stage / MARKER).write_bytes(MARKER_TEXT)
            replace(build, stage, output)
        finally:
            if stage.exists() and not stage.is_symlink():
                shutil.rmtree(stage, ignore_errors=True)
    finally:
        os.close(fd)
    print(f"built {len(list((output / 'plugins').glob('*.json')))} packages into {output}")


if __name__ == "__main__":
    run_main(main)
