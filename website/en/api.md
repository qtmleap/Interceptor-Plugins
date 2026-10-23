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

`Interceptor.attach(hooks)` registers the handlers in this file. The build derives host, path and method from its location and emits the declared request/response hooks into the manifest. Pass no target conditions or plugin ID to `attach`.

`actions` is the array of legacy Webhook actions returned by a hook. The `webhook` type describes an intended notification containing an `endpointId` and JSON data. Use an ID from `cfg.endpoints` for `endpointId`, rather than a destination URL. Synthetic tests display the action's contents without sending HTTP requests. Live processing does not save or deliver these returned Webhook actions. Use [Interceptor.send](#interceptor-send) to send GET requests to another API.

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

Reads the forwarded request after successful local forwarding. Input is read-only and includes edits made by `request.onEnter`. This does not guarantee that the server received or processed the request. Failed forwards do not call it.

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

Attempted body edits are errors. In synthetic tests, return actions based on the supplied traffic data to inspect them in the results. Live processing does not save or deliver the returned Webhook actions.

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

Reads the forwarded response after successful local forwarding. Input is read-only. Receipt or processing by the client is not guaranteed. Failed forwards do not call it.

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

Attempted body edits are errors. In synthetic tests, return actions based on the supplied traffic data to inspect them in the results. Live processing does not save or deliver the returned Webhook actions.

## fetch {#fetch}

Call standard global `fetch` inside an async `response.onLeave` callback and await
its response. Define the URL, method, headers and body in JS; no duplicate
`outbound` destination declaration is required.

Supported requests are GET/POST/PUT to public HTTPS hosts on port443 with JSON
request bodies. Query strings, redirects, streaming, compressed responses and
automatic cookies are unsupported. Responses expose `status`, `ok`, `bodyUsed`,
`text()` and `json()`; the body can be consumed once. Put async helper functions
inside `response.onLeave`. A fetching hook runs after forwarding, while existing
synchronous hooks retain their behavior.

Request bodies are limited to8KiB, responses to1MiB, and each invocation to
64requests and16MiB of response data. Runtime, concurrency and cancellation
limits also apply. Revocation or tunnel shutdown cancels pending work.
The existing synthetic-test screen sends no network traffic; use the offline
`interceptor-simulator run-package-fetch` fixture protocol for response tests.

## Interceptor.saveJSON {#save-json}

`await Interceptor.saveJSON(key, jsonText)` stores the JSON text `jsonText` under `key` in the plugin's own
file storage and returns `Promise<void>`. It requires `write.files: true` in the manifest (optional, default
`false`; schema 1 rejects it). Call it directly, not aliased or through `globalThis`, inside a
`response.onLeave` callback and await it. The build accepts only direct calls. A failed write rejects the
promise; runtime enforcement remains the host's responsibility.

## Interceptor.send {#interceptor-send}

`Interceptor.send(binding, { headers })` requests a GET to another API declared in the manifest `outbound` metadata. It records the request and returns `void` immediately. The app performs the actual HTTP request after hook validation; the hook cannot read the result, and the original traffic does not wait for delivery to finish. It does not implement `fetch`, Promise or `Response` semantics.

```ts
Interceptor.send('bearer', { headers: { authorization: 'Bearer ' + token } });
```

The second argument and its `headers` map are required; pass `{ headers: {} }` when no headers are needed. `SendOptions` accepts only `headers`, a plain object of string values whose names are listed in the declaration. The declaration fixes the URL and `GET` method, and requests have no body. Passing `url`, `method`, `body` or non-string header values is an error.

Use `send` from any of the four existing hooks when the captured traffic meets its normal JSON body and other eligibility rules. The original request method need not be `GET`. Keep one direct top-level `attach` call and call `send` directly inside an `onEnter` or `onLeave` function registered by `attach`. Calling `send` through another variable or as `Interceptor['send']` is rejected. It also cannot run while `attach` registers the hooks.

### Declaring outbound requests {#outbound-metadata}

Declare up to four named requests in `plugin.json`. Each one is exactly `url`, `method` (`"GET"`) and `headers` (up to eight lowercase names):

```json
"outbound": {
  "bearer": {
    "url": "https://interceptor-traffic-fixture.lemonandchan.workers.dev/auth/bearer",
    "method": "GET",
    "headers": ["authorization"]
  }
}
```

- Use an ASCII URL of at most 2048 bytes beginning with lowercase `https://`. It needs a lowercase DNS host and an explicit path starting with `/`. Omit the port, including `:443`, userinfo, query and fragment. The host needs at least two labels, with an ASCII letter somewhere in the final label. IP addresses, single-label hosts and `.local` or `.localhost` suffixes are rejected.
- The path is at most 1024 bytes. Only letters, digits, `-._~`, `!$&'()*+,;=`, `:`, `@` and `/` may appear literally; encode other bytes as valid percent escapes. Encoded UTF-8 bytes are allowed; decoded controls, DEL and backslashes are rejected.
- Interceptor sends only to the declared URL; there are no patterns, redirects or URL substitutions. Framing and hop-by-hop headers such as `host`, `proxy-*` names and `set-cookie` cannot be declared.
- The manifest is generated. `plugin.json` is the authored source; the build copies `outbound` into the manifest unchanged. Do not edit the generated manifest by hand.
- Adding or changing `outbound` changes the egress the user must approve. The fixed destinations are shown in the approval, and updated plugins need approval again.
- Each hook execution can record at most two actions, including legacy actions. For the same captured exchange and hook timing (for example, `response.onLeave`), all plugins together may send at most two GET requests. If the combined count exceeds two, or any validation before sending fails, all requests recorded for that timing are discarded. An invalid binding or undeclared header remains a validation error even if the script catches its exception. Network failures during the actual HTTP request are separate from pre-send validation errors and do not affect the original traffic.
- Take the first Cookie pair (`name=value`) from `Set-Cookie` and pass it in `cookie`, leaving out attributes such as `Path`. Cookies are never stored or sent automatically. Synthetic tests and the Rust simulator display recorded actions without delivering HTTP requests.

See the [fixture example](examples.md#outbound-example) for a token and cookie flow.

## Manifest and permissions

`plugin.json` declares plugin metadata and permissions. The schema 2 format described here is under development. These are the settings for the [sample](examples.md#request-summary); target conditions and file references are generated by the build:

<<< ../../plugins/request-summary/plugin.json{json}

Keep the plugin UUID `id` after publication and increment `version` for changes. Each plugin can contain up to 16 hook files. The folders and file name under `hooks/` specify each file’s target host, path and method. Each file makes one top-level `attach` call defining only the callbacks it needs. Declare only the required reads:

- `metadata`: fields such as `method`, `host`, `path` and `status`.
- `headers`: readable header names.
- `queryKeys`: readable query keys.
- `body.mode`: `none` omits the body; `json` exposes parsed JSON.

`write.requestBody` and `write.responseBody` allow JSON edits in the respective `onEnter`. Optional `write.files` (default `false`) allows `Interceptor.saveJSON`. Method, URL, headers and status cannot be changed.

`endpointBindings` is required and lists names used to construct webhook-shaped actions in synthetic tests; use `[]` when no names are needed. Synthetic tests may supply a test ID through `cfg.endpoints.preview`. Live processing supplies no endpoint IDs, so the examples return without an action when the ID is absent. Matching already checks the host and method. Settings are available as `cfg.settings`.

The generated package is `{manifest, sourceFiles}`. `manifest.matches` contains the host, method, exact path and phase references such as `hooks.request.onEnter`. `sourceFiles` maps file names to JavaScript source. Do not write `matches`, `hooks` or `sourceFiles` in `plugin.json`; the build rejects those fields.

## Execution and limits

Before each phase, Interceptor checks the traffic conditions and requested hook against the manifest, then evaluates only the matching file in a fresh runtime. Files that do not match are not executed. Variables outside a callback cannot carry state from `onEnter` to `onLeave`.

Live JSON processing requires an uncompressed UTF-8 `application/json` or `+json` body of at most 24 KiB. Compressed or large bodies, SSE, `Expect: 100-continue`, HEAD and bodyless responses bypass body hooks. Retained bodies, queued data, pending writes and bodies held by `onLeave` share a 64 KiB connection limit.

Upgrade requests and nested CONNECT requests within a decrypted connection receive `501` after earlier responses, then the connection closes. An unsolicited `101` response also closes the connection.

The app's shared processor runs one hook phase at a time, with at most eight waiting. An overloaded `onEnter` forwards the original traffic. Each connection allows at most four in-flight `onLeave` notifications; excess notifications are dropped while forwarding continues. Notification execution is not guaranteed.

Script errors and timeouts forward the original traffic. Revoked capture consent or plugin approval closes the connection. Only `response.onLeave` supports asynchronous `fetch`; other hooks remain synchronous. Timers, files, Node APIs and other browser APIs are unavailable.

Per invocation: 50 ms, 8 MiB heap, 128 KiB total plugin source, 64 KiB event, 8 KiB config, 32 KiB result and at most two actions.

## Types

Types help authoring. Runtime validation still enforces inputs and permissions.

<<< ../../types/interceptor.d.ts{ts}
