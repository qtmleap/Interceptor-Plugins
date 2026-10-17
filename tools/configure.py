#!/usr/bin/env python3
"""python3 tools/configure.py --root ROOT --repository OWNER/NAME --name NAME --url HTTPS_URL [--fingerprint HEX]

Turns a template checkout into your own repository: new repository and plugin UUIDs, your name, URL and
(optionally) your public key fingerprint. Sources and the upstream pin are preserved. Refuses to touch the
official repository, and either changes everything or nothing.
"""
from pathlib import Path

from repository_config import (ToolError, check_fingerprint, check_repository, canonical_url, dump_json,
                               is_display_name, load_config, load_reserved, load_samples, new_uuid,
                               origin_is_official, parse_args, run_main, same_repository, url_is_reserved,
                               validate_config, write_all_or_nothing, OFFICIAL_REPOSITORY)


def main(argv):
    options = parse_args(argv, ("--root", "--repository", "--name", "--url", "--fingerprint"), flags=("--fingerprint",))
    root = Path(options["--root"])
    if not root.is_dir():
        raise ToolError(f"root is not a directory: {root}")
    repository = check_repository(options["--repository"])
    if not is_display_name(options["--name"]):
        raise ToolError("--name must be 1 to 80 printable characters")
    url = canonical_url(options["--url"])
    fingerprint = check_fingerprint(options["--fingerprint"]) if "--fingerprint" in options else None

    reserved = load_reserved(root)
    if same_repository(repository, OFFICIAL_REPOSITORY):
        raise ToolError("refusing to reconfigure the official repository")
    if origin_is_official(root):
        raise ToolError("this checkout's Git origin is the official repository; configure your own copy")
    if url_is_reserved(url, reserved):
        raise ToolError("--url belongs to the official repository")
    if fingerprint is not None and fingerprint in reserved["fingerprints"]:
        raise ToolError("--fingerprint is a reserved official fingerprint")

    config = load_config(root)
    samples = load_samples(root)

    taken = {i.upper() for i in reserved["ids"]}
    repository_id = new_uuid(taken)
    taken.add(repository_id)
    files = {}
    for name, manifest, _ in samples:
        manifest = dict(manifest, id=new_uuid(taken))
        taken.add(manifest["id"])
        files[root / "manifests" / f"{name}.json"] = dump_json(manifest)

    config.update(id=repository_id, name=options["--name"], githubRepository=repository, repositoryURL=url,
                  publicKeyFingerprint=fingerprint)
    files[root / "repository-config.json"] = dump_json(validate_config(config))
    write_all_or_nothing(files)
    print(f"configured {repository} (repository id {repository_id}, {len(samples)} new plugin ids)")


if __name__ == "__main__":
    run_main(main)
