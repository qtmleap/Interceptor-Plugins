#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$TASK_ROOT"
command -v cargo >/dev/null || { echo 'Install Rust and Cargo (Ubuntu: apt install cargo rustc)' >&2; exit 1; }
command -v cc >/dev/null || { echo 'Install a C compiler (Ubuntu: apt install build-essential)' >&2; exit 1; }
command -v ar >/dev/null || { echo 'Install an archiver (Ubuntu: apt install binutils)' >&2; exit 1; }
tools/bootstrap.sh
cargo build --locked --offline --release --manifest-path tools/simulator/Cargo.toml --target-dir "$TASK_ROOT/.tools/simulator-target"
mkdir -p .tools/bin
cp .tools/simulator-target/release/interceptor-simulator .tools/bin/interceptor-simulator
mkdir -p build/simulator-release
cp .tools/bin/interceptor-simulator build/simulator-release/interceptor-simulator
cp tools/simulator/LICENSES.md build/simulator-release/LICENSES.md
