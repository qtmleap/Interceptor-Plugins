---
title: TypeScript authoring
lang: en-US
---

# TypeScript authoring

## Layout

Edit `src/NAME.ts`, `manifests/NAME.json` and `fixtures/cases.json` together. Every source needs a manifest with the same lowercase kebab-case name. Keep repository and plugin IDs stable after initial setup.

## Prerequisites

Use Bun %%BUN_VERSION%%, Python 3, OpenSSL and Git. The full `bun run check` requires a Mac with Xcode 27 / Swift 6.4 selected. On Linux, run `check:authoring`.

## Add a plugin

Copy an existing TypeScript source and manifest, giving both the same new lowercase kebab-case filename. Generate a unique manifest `id` once, then keep it stable after publication.

```sh
python3 -c 'import uuid; print(uuid.uuid4())'
```

Add at least one case per plugin to `fixtures/cases.json`. Each array entry has these fields:

| Key | Meaning |
|---|---|
| `name` | A readable test name |
| `plugin` | Filename without its extension, such as `request-summary` |
| `hook` | `request` or `response` |
| `event` | The input object passed to the hook |
| `expected` | The expected JSON return value, including `actions` |
| `expectError` | `"scriptError"` when an error is expected |

Specify exactly one of `expected` or `expectError`. Use the [real fixtures](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/fixtures/cases.json) as a guide, and cover both actions and no-action cases.

## Build and test

```sh
bun install --frozen-lockfile --ignore-scripts
bun run check:authoring   # works on Linux: types, Python/HTTPS, deterministic packages
bun run check             # Mac: real QuickJS, signing and configured-template checks
bun run build             # unsigned development packages in build/site/
```

- TypeScript 5.8.3 is pinned in `bun.lock`.
- `build/site/` must be absent or empty before `bun run build`. Remove only your previous generated output first.
- Never edit or commit the generated JavaScript in `build/scripts/`; packaging regenerates it from TypeScript every time.
- You never sign by hand: the publishing workflow supplies the key after tests pass.

## Update the version

Bump the manifest `version` whenever the source, compiled bytes or declarations change. The samples use v1 manifests at version 1.0.1; no new app schema is needed.

## Write a hook

Define a top-level `onRequest` or `onResponse` function matching the manifest subscription. Each plugin compiles independently, so function names may repeat between files.

<<< ../../src/request-summary.ts{ts}

This sample assumes the test `preview` binding and input. In a new hook, check that the binding and optional input fields exist; return `{ actions: [] }` when required values are missing.

See the [API reference](api.md) for the types.

::: warning Future design
`Interceptor.attach` / `rewriteJsonBody` appear in [HTTP Hook design](api.md#http-hooks) and the [future example](examples.md#future-http-hooks) but are unimplemented. They cannot currently be compiled, tested or published.
:::

## Runtime limits

The runtime evaluates one global script and calls the hook synchronously. Imports/exports, asynchronous code, promises, TypedArrays, and Node or browser APIs are unavailable. There is no `fetch`, console, filesystem, timer or module loader. Compilation rejects these common constructs, but it is not a security sandbox: the app's bounded QuickJS host is the execution boundary.

The preview returns at most two webhook intents, sends none of them, and does not connect scripts to captured traffic. SHA-256 covers the exact generated package bytes, and the signed index authenticates those hashes.

For publishing see [Publishing](publishing.md); for Linux development see [Development container](devcontainer.md).
