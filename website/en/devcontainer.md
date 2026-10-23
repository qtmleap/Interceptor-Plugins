---
title: Development environment
lang: en-US
---

# Development environment

## Use it

Install Docker, VS Code and the Dev Containers extension, then start Docker. Open this repository's root folder in VS Code, then run **Dev Containers: Reopen in Container** from the Command Palette. Dependencies install with `bun install --frozen-lockfile --ignore-scripts`. Plugin development does not require Xcode.

Write hooks in `plugins/NAME/hooks/{host}/{path}/{METHOD}.ts`, then generate and validate them with the commands below. See [Authoring](authoring.md) for the layout and callback examples.

```sh
bun run build
bun run simulator check build/scripts/request-summary/hooks/api.example.com/search/POST.js
bun run simulator run-package build/dev/plugins/request-summary.json request.onEnter fixtures/request-event.json fixtures/config.json
bun run check:authoring
```

`build` generates unsigned packages in `build/dev/plugins/`. Rerun it after editing sources. Compilation or packaging failure preserves the previous packages in `build/dev/`. The build also regenerates internal `build/scripts/` and `build/manifests/`, which may advance even if packaging fails.

The simulator's `check` command checks the generated JavaScript's syntax; `run-package` checks a hook from the package for the supplied input.

VS Code applies the SDK types independently to each hook file without emitting JavaScript. Build and authoring-check tasks are also available. Use `build` and `check:authoring` to validate file locations and the allowed syntax.

`bun run check` also covers signing and tamper rejection. It uses temporary test keys and needs no GitHub credentials or production key. `build:dev` remains a compatibility alias for `build`.

To initialize your own signed repository, sign in with `gh auth login` inside the container, then run `bun run setup`. See [Publishing](publishing.md).

## Resume setup after authentication stops it

Building and checking plugins do not themselves require GitHub credentials. This environment's initial setup can still stop at the commit guard's authentication check for protected Git operations.

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
