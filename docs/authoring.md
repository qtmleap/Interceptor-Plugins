# Plugin authoring

The authoring guide is maintained in the [VitePress guide](../website/en/authoring.md), with a [Japanese version](../website/authoring.md). See the [API reference](../website/en/api.md) for each hook's code and the [homepage](../website/en/index.md) for the client/Interceptor/server diagram.

Edit `src/NAME.ts`, `manifests/NAME.json` and `fixtures/cases.json` together. A source and manifest share the same lowercase kebab-case filename. Keep repository/plugin UUIDs stable after setup, and increase the manifest version when published content changes. New plugins use `schemaVersion: 2` with `matches`, explicit `read` grants and body `write` grants.

Use `Interceptor.attach(match, hooks)` to bind callbacks to a declared host/path/method match. Only matching callbacks run. The source can combine target/handler definitions into one plugin. See the actual [sample source](../src/request-summary.ts), [manifest](../manifests/request-summary.json) and [cases](../fixtures/cases.json).

## request.onEnter

Runs before forwarding the request. With JSON read access and `write.requestBody`, change `request.body` directly. The sample changes `{"query":"x","limit":50}` to `{"query":"x","limit":5}`.

## request.onLeave

Runs after successful local request forwarding; it does not guarantee server receipt or processing. It sees the forwarded body and cannot modify traffic. Return values are displayed in synthetic tests; the live adapter does not store or deliver actions.

## response.onEnter

Runs before returning the response. With JSON read access and `write.responseBody`, change `response.body` directly. `response.request` is a read-only view of the associated request.

## response.onLeave

Runs after successful local response forwarding; it does not guarantee client receipt or processing. Its traffic view is read-only. Failed forwarding never calls a leave hook.

## Build and emulate

On Linux or macOS, install the Bun version in `.bun-version`, Python 3, OpenSSL, Git, Rust 1.74 or later and a C compiler, or use the [development container](devcontainer.md). Xcode is not required for authoring, emulation, signing or publishing.

```sh
bun install --frozen-lockfile --ignore-scripts
bun run check
bun run simulator check build/scripts/request-summary.js
bun run simulator run build/scripts/request-summary.js request.onEnter fixtures/request-event.json fixtures/config.json --manifest manifests/request-summary.json
```

`check` parses syntax without evaluating source. `run` executes one hook using the supplied event/config and full v2 manifest, and prints actions plus any authorized body mutation. No webhook is sent. The built `.tools/bin/interceptor-simulator` runs independently on its matching OS/CPU with compatible system libraries. The same pinned CQuickJS bridge is used by the app and Rust binary.

TypeScript 5.8.3 is pinned in `bun.lock`. Each source compiles independently as a synchronous global script. Imports/exports, asynchronous code, promises, TypedArrays, Node/browser APIs, `fetch`, console, filesystem and timers are unavailable. Each phase starts a fresh VM. The app also enforces matching, read/write grants and resource limits; compilation is not the execution boundary.

`build/scripts/` and `build/site/` are generated and ignored. Packaging recompiles sources and fails on type errors. `bun run build` writes unsigned development packages into an absent or empty `build/site/`; preserve/remove only your own prior output before rebuilding. Legacy schema 1 fixtures remain in `fixtures/legacy-v1/` for compatibility tests and cannot activate on live traffic.

For your own signed feed, create a public GitHub template repository, run `bun run setup`, then follow [publishing](../website/en/publishing.md) and [maintenance/recovery](maintaining.md). Setup itself does not commit, push or deploy. Wait for signed live verification before registering the printed URL.
