#!/usr/bin/env python3
"""Read-only route discovery for the Bun compiler; never evaluates authored code."""
import json
from pathlib import Path
from repository_config import parse_args, run_main
from route_sources import discover


def main(argv):
    options = parse_args(argv, ('--root',))
    print(json.dumps(discover(Path(options['--root'])), ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    run_main(main)
