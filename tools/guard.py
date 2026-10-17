#!/usr/bin/env python3
"""python3 tools/guard.py --root ROOT --repository OWNER/NAME --ref refs/heads/main

Signed-deployment identity check, run before any key is touched. Passes only when the configured repository
matches the argument, a signing fingerprint is configured, and official identities (reserved in
tools/reserved.json) are used by the official repository and nobody else.
"""
from pathlib import Path

from repository_config import (OFFICIAL_REPOSITORY, ToolError, check_repository, load_config, load_reserved,
                               load_samples, parse_args, run_main, same_repository, url_is_reserved)


def main(argv):
    options = parse_args(argv, ("--root", "--repository", "--ref"))
    root = Path(options["--root"])
    if not root.is_dir():
        raise ToolError(f"root is not a directory: {root}")
    repository = check_repository(options["--repository"])
    if options["--ref"] != "refs/heads/main":
        raise ToolError("signed deployment requires refs/heads/main")

    config, reserved = load_config(root), load_reserved(root)
    plugin_ids = [manifest["id"].upper() for _, manifest, _ in load_samples(root)]
    if not same_repository(config["githubRepository"], repository):
        raise ToolError(f"configured repository {config['githubRepository']} does not match {repository}")
    fingerprint = config["publicKeyFingerprint"]
    if fingerprint is None:
        raise ToolError("publicKeyFingerprint is required for a signed deployment")

    ids = [config["id"].upper()] + plugin_ids
    if len(set(ids)) != len(ids):
        raise ToolError("repository and plugin ids must be distinct")
    reserved_ids = {i.upper() for i in reserved["ids"]}
    if same_repository(repository, OFFICIAL_REPOSITORY):
        if fingerprint not in reserved["fingerprints"]:
            raise ToolError("official signing fingerprint is not reserved in tools/reserved.json")
        if not set(ids) <= reserved_ids:
            raise ToolError("official repository uses an id that is not reserved in tools/reserved.json")
        if not url_is_reserved(config["repositoryURL"], reserved):
            raise ToolError("official repository URL is not reserved in tools/reserved.json")
    else:
        if reserved_ids & set(ids):
            raise ToolError("official repository or plugin ids must not be reused; run tools/configure.py")
        if url_is_reserved(config["repositoryURL"], reserved):
            raise ToolError("the official repository URL must not be reused; run tools/configure.py")
        if fingerprint in reserved["fingerprints"]:
            raise ToolError("an official signing key fingerprint must not be reused")
    print(f"identity ok: repository={repository} id={config['id']} url={config['repositoryURL']} fingerprint={fingerprint}")


if __name__ == "__main__":
    run_main(main)
