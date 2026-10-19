---
title: API reference
lang: en
---

<script setup>
import HookFlow from '../.vitepress/components/HookFlow.vue'
</script>

# API reference

<HookFlow locale="en" />

## Interceptor.attach

`Interceptor.attach(hooks)` registers the handlers in this file. The build derives host, path and method from its location and emits the declared request/response hooks into the manifest. JavaScript passes no target conditions or IDs.

Place this code in `hooks/api.example.com/search/POST.ts` to handle `POST https://api.example.com/search`. Interceptor uses the generated manifest to select the matching route and hook, then loads and executes the corresponding JavaScript file.

```ts
Interceptor.attach({
  request: {
    onEnter(req, cfg) {
      if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) return;
      req.body.limit = 5;
    },
    onLeave(req, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook', endpointId,
        json: { path: req.path! }
      }] };
    }
  },
  response: {
    onEnter(res, cfg) {
      if (!res.body || typeof res.body !== 'object' || Array.isArray(res.body)) return;
      res.body.maintenance = true;
    },
    onLeave(res, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook', endpointId,
        json: { status: res.status! }
      }] };
    }
  }
});
```

Define only the callbacks you need. Request hooks receive `(req, cfg)` and response hooks receive `(res, cfg)`. `req` and `res` contain traffic data; `cfg` contains plugin configuration. Read the manifest's `settings` through `cfg.settings`. Synthetic-test endpoint bindings are available through `cfg.endpoints`.

When you do not use configuration, omit the second parameter: `onEnter(res) { ... }`. `res.request` refers to the associated request.

### Files and target conditions {#matching}

The build generates conditions and file references from `hooks/{host}/{path}/{METHOD}.ts`. Use `hooks/{host}/{METHOD}.ts` for the root path, for example `hooks/api.example.com/GET.ts`.

Use lowercase host names and uppercase HTTP methods. Paths are exact and case-sensitive; query strings are excluded. Dynamic paths, wildcards, trailing-slash paths, non-ASCII characters and `%` in paths are not supported by this directory convention. Unsupported paths are not normalized into another route.

Add another file at the corresponding location to handle another target in the same plugin. See [Write a plugin](authoring.md).

## request.onEnter {#request-onenter}

Runs before forwarding a request upstream. With `read.body.mode: "json"` and `write.requestBody: true`, edit the parsed JSON directly:

```ts
Interceptor.attach({
  request: {
    onEnter(req, cfg) {
      if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) return;
      req.body.limit = 5;
    }
  }
});
```

Assign `req.body = { query: 'example', limit: 5 }` to replace the entire body. Unchanged bodies retain their original bytes. No author-defined rewrite helper is needed.

## request.onLeave {#request-onleave}

Runs after successful local forwarding of the request. It sees edits made by `request.onEnter`. This does not guarantee that the server received or processed the request. Failed forwards do not call it.

```ts
Interceptor.attach({
  request: {
    onLeave(req, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook', endpointId,
        json: { method: req.method!, path: req.path! }
      }] };
    }
  }
});
```

Input is read-only; attempted body edits are errors. Returned actions appear in synthetic-test results. Live processing does not save or deliver them, despite the `webhook` type name.

## response.onEnter {#response-onenter}

Runs before forwarding a response downstream. With `read.body.mode: "json"` and `write.responseBody: true`, edit the response JSON:

```ts
Interceptor.attach({
  response: {
    onEnter(res, cfg) {
      if (!res.body || typeof res.body !== 'object' || Array.isArray(res.body)) return;
      res.body.maintenance = true;
    }
  }
});
```

`res.request` is read-only. It cannot change a request that has already been forwarded.

## response.onLeave {#response-onleave}

Runs after successful local forwarding of a response. Receipt or processing by the client is not guaranteed. Failed forwards do not call it.

```ts
Interceptor.attach({
  response: {
    onLeave(res, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook', endpointId,
        json: { path: res.request.path!, status: res.status! }
      }] };
    }
  }
});
```

Input is read-only. Returned intents appear in synthetic tests. Live processing does not save or deliver them.

## Manifest and permissions

`plugin.json` declares plugin metadata and permissions. The schema 2 format described here is under development. These are the settings for the [sample](examples.md#request-summary); target conditions and file references are generated by the build:

<<< ../../plugins/request-summary/plugin.json{json}

Keep the plugin UUID `id` after publication and increment `version` for changes. Each plugin can contain up to 16 route files. Each file makes one top-level `attach` call defining only the callbacks it needs. Declare only the required reads:

- `metadata`: fields such as `method`, `host`, `path` and `status`.
- `headers`: readable header names.
- `queryKeys`: readable query keys.
- `body.mode`: `none` omits the body; `json` exposes parsed JSON.

`write.requestBody` and `write.responseBody` allow JSON edits in the respective `onEnter`. Method, URL, headers and status cannot be changed.

`endpointBindings` is required and lists names used to construct webhook-shaped actions in synthetic tests; use `[]` when no names are needed. Synthetic tests may supply a test ID through `cfg.endpoints.preview`. Live processing supplies no endpoint IDs, so the examples return without an action when the ID is absent. Matching already checks the host and method. Settings are available as `cfg.settings`.

The generated package is `{manifest, sourceFiles}`. `manifest.matches` contains the host, method, exact path and phase references such as `hooks.request.onEnter`. `sourceFiles` maps file names to JavaScript source. Do not write `matches`, `hooks` or `sourceFiles` in `plugin.json`; the build rejects those fields.

## Execution and limits

Before each phase, Interceptor checks the traffic conditions and requested hook against the manifest, then evaluates only the matching file in a fresh runtime. Files that do not match are not executed. Variables outside a callback cannot carry state from `onEnter` to `onLeave`.

Live JSON processing requires an uncompressed UTF-8 `application/json` or `+json` body of at most 24 KiB. Compressed or large bodies, SSE, protocol upgrades, `Expect: 100-continue`, HEAD and bodyless responses bypass body hooks. Buffered or queued connection data is bounded at 64 KiB.

Script errors and timeouts forward the original traffic. Revoked approval closes the connection. Execution is synchronous: no `fetch`, promises, timers, files, Node APIs or browser APIs.

Per invocation: 50 ms, 8 MiB heap, 128 KiB total plugin source, 64 KiB event, 8 KiB config, 32 KiB result and at most two actions.

## Types

Types help authoring. Runtime validation still enforces inputs and permissions.

<<< ../../types/interceptor.d.ts{ts}
