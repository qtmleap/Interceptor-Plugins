---
title: Development environment
lang: en-US
---

# Development environment

## Use it

Have Docker and VS Code ready, then run **Dev Containers: Reopen in Container**. Dependencies install with `bun install --frozen-lockfile --ignore-scripts`.

```sh
bun run check
bun run build
```

`check` covers compilation, package generation, QuickJS execution, signing and tamper rejection. It uses temporary test keys and needs no GitHub credentials or production key. The build output must be absent or empty.

To initialize your own signed repository, sign in with `gh auth login` inside the container, then run `bun run setup`. See [Publishing](publishing.md).

## Resume setup after authentication stops it

Attach to the existing running container and run these commands inside it. After GitHub login, `commitguard/setup` repeats the authentication check required for Git operations. `postCreateCommand.sh` then resumes initial setup, including dependency installation.

```sh
cd /home/vscode/app
gh auth login -h github.com
/usr/local/share/commitguard/setup
bash .devcontainer/postCreateCommand.sh
```

## Limits

- The commit guard requires a verified human GitHub login and keeps Git blocked until activation succeeds. If creation stops at authentication, in the running container run `gh auth login -h github.com`, then `/usr/local/share/commitguard/setup`.
- No host credentials or signing keys are mounted. VS Code itself may still forward Git configuration, a credential helper or an SSH agent; review those VS Code settings if you need isolation.

The detailed layout and the upstream license are in [docs/devcontainer.md](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/docs/devcontainer.md).
