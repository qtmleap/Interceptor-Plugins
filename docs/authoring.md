# Plugin authoring

The [VitePress guide](../website/en/authoring.md) and its [Japanese version](../website/authoring.md) explain how to write and test plugins. See the [API reference](../website/en/api.md) for the four hooks and [What is Interceptor?](../website/en/what-is-interceptor.md) for the client/Interceptor/server flow. The schema 2 format and live HTTP hooks described here are under development.

Keep each plugin in `plugins/NAME/`:

```text
plugins/request-summary/
├── plugin.json
└── hooks/
    └── api.example.com/
        └── search/
            └── POST.ts
```

`plugin.json` declares metadata, explicit `read` and body `write` grants, `endpointBindings` and `settings`. Keep the plugin UUID stable after setup and increment its version when published content changes. Do not write `matches`, `hooks` or `sourceFiles` in this file. Optionally set `publishedAt` to the date you declare for the release, in UTC as `yyyy-MM-ddTHH:mm:ssZ` (for example `2026-10-21T09:30:00Z`). You write it yourself; the build copies it unchanged and never generates it. Omit it if you do not want to show a date.

Optionally set `icon` to a PNG or WebP inside the plugin folder (for example `assets/Icon.webp`; lowercase `.png`/`.webp` suffix, ASCII path up to 256 bytes, file 1 to 65536 bytes, width and height each 1 to 1024, not animated). The build reads only regular files reached through real directories (no symlinks) and embeds the bytes in the package as `assets` (`{icon path: base64}`); without an icon `assets` is omitted. Validation is structural and does not prove the image decodes.

The location `hooks/HOST/PATH/METHOD.ts` selects an exact host, path and method. For `/`, use `hooks/HOST/METHOD.ts`. Host names are lowercase; methods are uppercase. Paths are case-sensitive. Add another file to handle another API, with up to 16 route files per plugin.

Each file makes one top-level `Interceptor.attach({ request: { ... }, response: { ... } })` call. Pass only the callbacks; there is no JavaScript match object, match ID or filename argument. The build derives routing from file locations and callback definitions. See the [sample source](../plugins/request-summary/hooks/api.example.com/search/POST.ts), [metadata](../plugins/request-summary/plugin.json) and [cases](../fixtures/cases.json).

## request.onEnter

Runs before forwarding the request. With JSON read access and `write.requestBody`, change `request.body` directly. The sample changes `{"query":"x","limit":50}` to `{"query":"x","limit":5}`.

## request.onLeave

Runs after successful local request forwarding; it does not guarantee server receipt or processing. It sees the forwarded body and cannot modify traffic. Return values are displayed in synthetic tests; live processing does not store or deliver actions.

## response.onEnter

Runs before returning the response. With JSON read access and `write.responseBody`, change `response.body` directly. `response.request` is a read-only view of the associated request.

## response.onLeave

Runs after successful local response forwarding; it does not guarantee client receipt or processing. Its traffic view is read-only. Failed forwarding never calls a leave hook.

## Build and emulate

On Linux or macOS, install the Bun version in `.bun-version`, Python 3, OpenSSL, Git, Rust 1.74 or later and a C compiler, or use the [development environment](devcontainer.md). Xcode is not required for authoring, emulation, signing or publishing.

```sh
bun install --frozen-lockfile --ignore-scripts
bun run check
bun run build
bun run simulator check build/scripts/request-summary/hooks/api.example.com/search/POST.js
bun run simulator run-package build/site/plugins/request-summary.json request.onEnter fixtures/request-event.json fixtures/config.json
```

`check` parses syntax without evaluating source. `run-package` selects a file using the full package manifest and the requested phase, then prints actions and any authorized body mutation. Nonmatching files are not executed. No webhook is sent. The built `.tools/bin/interceptor-simulator` runs independently on its matching OS/CPU with compatible system libraries. The app and Rust binary use the same pinned CQuickJS bridge.

TypeScript 5.8.3 is pinned in `bun.lock`. Each source compiles independently as a synchronous global script. Imports/exports, asynchronous code, promises, TypedArrays, Node/browser APIs, `fetch`, console, filesystem and timers are unavailable. Each phase starts a fresh VM. The app also enforces matching, read/write grants and resource limits; compilation is not the execution boundary.

The build generates `build/manifests/NAME.json` and `build/scripts/NAME/`. A schema 2 package is `{manifest, sourceFiles}`. `manifest.matches` contains the host, method, exact path and nested hook-to-file references; `sourceFiles` maps relative file names to JavaScript. Packaging retains all emitted files and fails on type errors.

`build/manifests/`, `build/scripts/` and `build/site/` are generated and ignored. `bun run build` writes unsigned development packages into an absent or empty `build/site/`; preserve or remove only your own prior output before rebuilding. The authored `plugins/` directory is not a publish directory. Published packages are written to `build/site/plugins/NAME.json`.

For your own signed feed, create a public GitHub template repository, run `bun run setup`, then follow [publishing](../website/en/publishing.md) and [maintenance/recovery](maintaining.md). Setup itself does not commit, push or deploy. Wait for signed live verification before registering the printed URL.
