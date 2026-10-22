#!/usr/bin/env python3
"""Prepare generated manifests and JavaScript for documentation source includes. No runtime or signing build."""
from pathlib import Path
from repository_config import load_samples, parse_args, run_main


def main(argv):
    options = parse_args(argv, ("--root",))
    samples = load_samples(Path(options["--root"]))
    print(f"prepared {len(samples)} documentation examples")


if __name__ == '__main__':
    run_main(main)
