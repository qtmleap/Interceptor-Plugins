#!/usr/bin/env bash
set -euo pipefail
cd /home/vscode/app
if [[ -L node_modules ]]; then
  echo 'The dependency volume must be a directory, not a symlink.' >&2
  exit 1
fi
sudo chown -R -- "$(id -u):$(id -g)" node_modules
bun install --frozen-lockfile --ignore-scripts
