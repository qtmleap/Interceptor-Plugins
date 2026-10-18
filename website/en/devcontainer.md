---
title: Development container
lang: en-US
---

# Development container

A development environment adapted from `qtmleap/devcontainers`. It provides Ubuntu 24.04, Bun %%BUN_VERSION%%, Python 3, OpenSSL and GitHub CLI.

## Use it

Have Docker and VS Code ready, then run **Dev Containers: Reopen in Container**. Dependencies install with `bun install --frozen-lockfile --ignore-scripts`.

```sh
bun run check:authoring
bun run build
```

`check:authoring` runs the Python tool tests, HTTPS fixtures, TypeScript compilation and deterministic package generation. It needs no GitHub credentials or signing key. `build/site/` must be absent or empty.

## Resume setup after authentication stops it

Attach to the existing running container and run these commands inside it. The final command resumes the lifecycle and installs dependencies after login.

```sh
cd /home/vscode/app
gh auth login -h github.com
/usr/local/share/commitguard/setup
bash .devcontainer/postCreateCommand.sh
```

## Limits

- The full `bun run check` (real QuickJS, signing, configured-template checks) runs on a Mac with Xcode 27 / Swift 6.4. It stays mandatory in CI before signing and publishing; Linux checks do not replace it.
- The first `bun run setup` also runs on the Mac because it uses CryptoKit. Unsupported hosts are rejected before any state changes.
- The commit guard requires a verified human GitHub login and keeps Git blocked until activation succeeds. If creation stops at authentication, in the running container run `gh auth login -h github.com`, then `/usr/local/share/commitguard/setup`.
- No host credentials or signing keys are mounted. VS Code itself may still forward Git configuration, a credential helper or an SSH agent; review those VS Code settings if you need isolation.

The detailed layout and the upstream license are in [docs/devcontainer.md](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/docs/devcontainer.md).
