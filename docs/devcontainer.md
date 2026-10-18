# Container development

The configuration is adapted from [qtmleap/devcontainers](https://github.com/qtmleap/devcontainers/tree/7d1931f8d33e49dee3775b1d893297ced0c639bf), revision `7d1931f8d33e49dee3775b1d893297ced0c639bf`: `examples/hono-node/.devcontainer/` and the shared editor configuration. The upstream MIT notice is retained in [licenses/devcontainers-LICENSE](licenses/devcontainers-LICENSE).

Open this checkout with VS Code **Dev Containers: Reopen in Container**. Docker must be running. The Ubuntu 24.04 container supplies Bun 1.3.6, Python 3, OpenSSL, GitHub CLI and the upstream `ghcr.io/tkgstrator/commitguard:1` feature. Base/Bun images are pinned by digest; feature resolution is recorded in the Dev Container lockfile. The workspace is mounted at `/home/vscode/app`, with a separate Linux `node_modules` volume.

The commit guard requires a verified human GitHub login and keeps Git blocked until activation succeeds. This configuration adds no host credential or signing-key mounts. VS Code Dev Containers can separately copy Git configuration, forward its host credential helper and forward an SSH agent, according to local client settings. This project does not change those settings: developers who require credential isolation should review `dev.containers.copyGitConfig`, `dev.containers.gitCredentialHelperConfigLocation` and SSH-agent forwarding before reopening. CLI-based verification does not establish the VS Code client's forwarding behavior. If initial creation stops at authentication, open a terminal in the existing container (use **Dev Containers: Attach to Running Container** if needed) and complete recovery there:

```sh
cd /home/vscode/app
gh auth login -h github.com
/usr/local/share/commitguard/setup
bash .devcontainer/postCreateCommand.sh
```

Keep that container: rebuilding replaces its private home and loses this login. From a host with the Dev Containers CLI, `devcontainer run-user-commands --workspace-folder /absolute/path/to/checkout` can instead resume the configured lifecycle against the same running container.

As in the upstream template, activation installs its managed policy/skill files in the workspace; review any instruction-file changes. The generated `.codex/` and `.claude/` state is ignored.

After creation, dependencies install with `bun install --frozen-lockfile --ignore-scripts`. For daily development:

```sh
bun run check:authoring
bun run build
```

The portable check covers Python tool tests, actual HTTPS fixtures, TypeScript compilation and deterministic packages. It requires no GitHub credentials or signing key. The build output directory must be absent or empty; preserve/remove only your previous generated `build/site/` before rebuilding.

Run `bun run check` on a Mac with Xcode 27 / Swift 6.4 for the complete QuickJS, signature and configured-template checks. Those checks remain mandatory in CI before signing/publishing. Linux authoring checks do not replace them. Initial `bun run setup` also runs on the Mac because the pinned publisher uses CryptoKit; it rejects unsupported hosts before changing local or remote state.

Project adaptations keep the upstream Compose/workspace/dependency-volume layout and guarded Git, but pin Bun directly in the Dockerfile rather than using an unversioned installer. The Hono app, Biome/submodule, optional agent CLIs, host configuration/credential mounts, Docker socket, forwarded ports, branch pruning and automatic authentication are omitted. Shared VS Code defaults are retained with built-in TypeScript formatting and the workspace compiler, without adding a formatter dependency. No upstream development configuration is synced automatically.
