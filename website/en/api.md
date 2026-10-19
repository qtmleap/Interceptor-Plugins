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

`Interceptor.attach(match, hooks)` associates target traffic with callbacks. The runtime calls a callback only when the host, path, method and other declared conditions match. A source can define the targets and processing for one plugin.

```ts
const search: Interceptor.Match = {
  hosts: ['api.example.com'],
  methods: ['POST'],
  path: { kind: 'exact', value: '/search' }
};

Interceptor.attach(search, {
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

### Matching

Each `match` must equal an entry in the manifest's `matches`. Undeclared registrations are rejected at runtime.

- `hosts`: exact host names; no wildcards or regular expressions.
- `methods`: allowed HTTP methods; omit to accept all methods.
- `path`: `exact` or `prefix`, applied to the path without its query string.
- `status`: inclusive `min` and `max` response status range. Use this for response callbacks only.

Different fields combine with AND; values in an array combine with OR. For example, a 500–599 status condition works without `status` in `read.metadata`. The grant is needed to read `res.status` inside a callback.

## request.onEnter {#request-onenter}

Runs before forwarding a request upstream. With `read.body.mode: "json"` and `write.requestBody: true`, edit the parsed JSON directly:

```ts
Interceptor.attach(search, {
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
Interceptor.attach(search, {
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
Interceptor.attach(search, {
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
Interceptor.attach(search, {
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

New plugins use `schemaVersion: 2`. This is the manifest for the [sample](examples.md#request-summary):

<<< ../../manifests/request-summary.json{json}

Keep the plugin UUID `id` after publication and increment `version` for changes. `matches` accepts 1–16 entries; source accepts up to 16 `attach` calls. Declare only the required reads:

- `metadata`: fields such as `method`, `host`, `path` and `status`.
- `headers`: readable header names.
- `queryKeys`: readable query keys.
- `body.mode`: `none` omits the body; `json` exposes parsed JSON.

`write.requestBody` and `write.responseBody` allow JSON edits in the respective `onEnter`. Method, URL, headers and status cannot be changed.

`endpointBindings` is required and lists names used to construct webhook-shaped actions in synthetic tests; use `[]` when no names are needed. Synthetic tests may supply a test ID through `cfg.endpoints.preview`. Live processing supplies no endpoint IDs, so the examples return without an action when the ID is absent. Matching already checks the host and method. Settings are available as `cfg.settings`.

Legacy schema 1 `onRequest` and `onResponse` remain available for existing synthetic tests. Do not define them in a four-hook source. Schema 1 packages cannot be activated on live traffic.

## Execution and limits

Each phase gets a fresh runtime and reevaluates the source. Variables outside a callback cannot carry state from `onEnter` to `onLeave`.

Live JSON processing requires an uncompressed UTF-8 `application/json` or `+json` body of at most 24 KiB. Compressed or large bodies, SSE, protocol upgrades, `Expect: 100-continue`, HEAD and bodyless responses bypass body hooks. Buffered or queued connection data is bounded at 64 KiB.

Script errors and timeouts forward the original traffic. Revoked approval closes the connection. Execution is synchronous: no `fetch`, promises, timers, files, Node APIs or browser APIs.

Per invocation: 50 ms, 8 MiB heap, 128 KiB source, 64 KiB event, 8 KiB config, 32 KiB result and at most two actions.

## Types

Types help authoring. Runtime validation still enforces inputs and permissions.

<<< ../../types/interceptor.d.ts{ts}
