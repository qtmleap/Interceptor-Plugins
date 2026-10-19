---
title: Authoring
lang: en
---

<script setup>
import HookFlow from '../.vitepress/components/HookFlow.vue'
</script>

# Authoring

Create a plugin that changes JSON on `POST https://api.example.com/search` before forwarding a request or response. Its file location selects the traffic to process.

The schema 2 format and live HTTP hooks described in this guide are under development.

## Tools

Linux and macOS use the same commands. Install Bun %%BUN_VERSION%%, Python 3, OpenSSL, Git, Rust and a C compiler, or use the [development environment](devcontainer.md). Creating, testing and signing plugins does not require Xcode.

## Files

Keep each plugin in `plugins/NAME/`. Declare its name, version and read/write permissions in `plugin.json`, and write its processing under `hooks/`. Do not list target conditions or source files in `plugin.json`.

```text
plugins/request-summary/
├── plugin.json
└── hooks/
    └── api.example.com/
        └── search/
            └── POST.ts
```

The location `hooks/{host}/{path}/{METHOD}.ts` selects the traffic. This example handles `POST https://api.example.com/search`. Use `hooks/api.example.com/GET.ts` for `GET https://api.example.com/`, or `hooks/api.example.com/v1/items/PUT.ts` for `PUT https://api.example.com/v1/items`.

To handle another API, add a file at its corresponding location. The build generates the manifest's target conditions and hook-to-file references from these locations and callback definitions.

Generate a plugin UUID once and retain it after publication:

```sh
python3 -c 'import uuid; print(uuid.uuid4())'
```

<HookFlow locale="en" />

## Edit JSON {#edit-json}

In `POST.ts`, pass only the callbacks to `Interceptor.attach`:

```ts
Interceptor.attach({
  request: {
    onEnter(req, cfg) {
      if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) return;
      req.body.limit = 5;
    }
  },
  response: {
    onEnter(res, cfg) {
      if (!res.body || typeof res.body !== 'object' || Array.isArray(res.body)) return;
      res.body.maintenance = true;
    }
  }
});
```

`req` is the request, `res` is the response, and `cfg` is plugin configuration. This example does not use `cfg`; you can omit the second parameter when configuration is unnecessary.

These callbacks change fields only when the body is a JSON object. Missing bodies and arrays remain unchanged. Interceptor checks the host, path and method using the generated manifest.

Declare data access in `plugin.json`. Editing JSON requires both JSON read permission and the write permission for the corresponding traffic leg:

<<< ../../plugins/request-summary/plugin.json{json}

A request body changes from:

```json
{"query":"x","limit":50}
```

to:

```json
{"query":"x","limit":5}
```

A response body changes from:

```json
{"ok":true}
```

to:

```json
{"ok":true,"maintenance":true}
```

`body` is parsed JSON. Assign fields or work with arrays directly, according to your API's input shape. Use `request.onLeave` and `response.onLeave` for processing after successful local forwarding. See [the four callbacks](api.md#request-onenter).

## Test cases

Add input and expected output in `fixtures/cases.json`. Run these cases with `bun run check`. V2 uses `phase` with one of the four hook names:

```json
{
  "name": "search limit changed to five on enter",
  "plugin": "request-summary",
  "phase": "request.onEnter",
  "event": {
    "phase": "request.onEnter",
    "request": {
      "method":"POST", "host":"api.example.com", "path":"/search",
      "body":{"query":"x","limit":50}
    }
  },
  "expected": {"actions":[], "mutation":{"body":{"query":"x","limit":5}}}
}
```

The runtime produces `mutation`; callback authors only edit `body`. Use `expectError: "scriptError"` instead of `expected` to test failure. Cover unmatched traffic and forbidden edits in a leave callback.

## Build and validate

```sh
bun install --frozen-lockfile --ignore-scripts
bun run build:dev
bun run check:authoring
bun run check
```

`build:dev` generates unsigned packages in `build/dev/plugins/NAME.json`. Rerun it after editing sources. Compilation or packaging failure preserves the previous packages in `build/dev/`. The build also regenerates internal `build/scripts/` and `build/manifests/`, which may advance even if packaging fails.

`check:authoring` runs type checks, tool tests and package generation; `check` also executes `fixtures/cases.json` and checks signatures and tamper detection. The existing `bun run build` writes to `build/site/`, which must be absent or empty.

VS Code checks each hook file with the SDK types without emitting JavaScript. Build and authoring-check tasks are available. The build still validates file locations and allowed syntax.

The build writes the manifest to `build/manifests/NAME.json` and JavaScript to `build/scripts/NAME/`. The package is `{manifest, sourceFiles}`: `manifest.matches` contains target conditions and hook-to-file references, while `sourceFiles` contains each file’s JavaScript. Do not edit or commit generated files. Increment `version` in `plugin.json` when published content changes.

## Rust simulator

`interceptor-simulator` uses the app's QuickJS bridge for syntax and execution checks. Its first build fetches pinned source and requires Rust and a C compiler.

```sh
bun run simulator check build/scripts/request-summary/hooks/api.example.com/search/POST.js
bun run simulator run-package build/dev/plugins/request-summary.json request.onEnter fixtures/request-event.json fixtures/config.json
```

Both input files are included in this repository. `fixtures/request-event.json` supplies traffic data, while `fixtures/config.json` supplies the callback's second argument:

<<< ../../fixtures/request-event.json{json}

<<< ../../fixtures/config.json{json}

Copy and edit them for your API. `fixtures/cases.json` also contains expectations and cannot be passed directly to `run-package`.

The simulator's `check` subcommand parses generated JavaScript without executing the hook. Its `run-package` subcommand uses the package’s manifest to select the file for the input traffic and requested hook, then validates permissions and JSON changes. Nonmatching files are not executed. The simulator does not forward traffic or deliver webhooks. Verify actual network ordering in the app.

After building, run `.tools/bin/interceptor-simulator` directly. A binary for the same OS/CPU does not require Bun, Python, Rust or Xcode at runtime. Linux still requires compatible system libraries.

## Publish

Packages use Ed25519 signing. Register the key with [Publishing](publishing.md); CI signs and distributes on pushes to master.
