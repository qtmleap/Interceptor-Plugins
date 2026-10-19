---
title: API reference
lang: en-US
---

# API reference

## Synchronous v1 synthetic preview

Hooks are called synchronously and return `{ actions: [...] }`. `actions` holds at most two webhook intents. They are displayed, never delivered; there is no live capture or background execution. The types aid authoring and are neither an input validator nor a permission grant: the app validates input and result limits at runtime. `read` declarations are validated and stored, but do not filter synthetic input.

## Type declarations

<<< ../../types/interceptor.d.ts{ts}

## Manifest fields

Real manifests are in [Examples](examples.md).

| Field | Meaning |
|---|---|
| `schemaVersion` | Always `1` |
| `id` | The plugin UUID. Keep it stable after publishing |
| `name` / `version` | Display name, and a version you bump on every change |
| `subscriptions` | `phase` (`request.headers`, `request.completed`, `response.headers`, `response.completed`) and `match` |
| `read` | Grants: what the hook may read |
| `endpointBindings` | Names of webhook destinations |
| `settings` | Setting values (empty in the samples) |

`match` accepts `hosts`, `methods`, `path` and `status`. A path is `{ "kind": "exact", "value": "/api/items" }` or `{ "kind": "prefix", "value": "/api/" }`; status uses a `min`/`max` range. The synthetic test does not apply `match`, so check the same conditions inside the hook.

## onRequest {#onrequest}

`onRequest(event, config)` runs synchronously when you select the request hook in a synthetic test. The manifest declares request phases, but automatic subscription execution is unimplemented. Optional properties of `event.request` depend on the input, so check that they exist and return `{ actions: [] }` when a required value is missing. The synthetic test does not apply the manifest `match`, so keep the same conditions inside the hook. The return value is a display-only webhook intent; it cannot rewrite or control the request.

<<< ../../src/request-summary.ts{ts}

## onResponse {#onresponse}

`onResponse(event, config)` runs synchronously when you select the response hook in a synthetic test. The manifest declares response phases. Check optional `event.response` properties the same way and test status, host and similar conditions inside the hook. The return value is display-only; the response is not changed.

<<< ../../src/server-error-filter.ts{ts}

## Read grants

Declare only what you need under `read`:

- `metadata`: such as `method`, `host`, `path`, `status`
- `headers`: the header names to read
- `queryKeys`: the query keys to read
- `body.mode`: `none` reads no body

`read` is currently a validated, stored declaration. Synthetic tests pass the input JSON without filtering it through these declarations. A declaration does not grant live traffic access.

## Endpoint bindings

A name declared in `endpointBindings` is resolved as `config.endpoints[name]`, giving the destination ID. Tests use the values in `fixtures/config.json`. Put that value in the intent's `endpointId`, and handle the `undefined` case.

## HTTP Hook design {#http-hooks}

::: info Unimplemented API
This is a future HTTP Hook design. The current runtime has neither `Interceptor.attach` nor `rewriteJsonBody`; pasting this code into a synthetic test will not work. Use `onRequest` / `onResponse` above for code built and verified with today's template.
:::

`Interceptor.attach` is inspired by [Frida's Interceptor](https://frida.re/docs/javascript-api/#interceptor), which registers `onEnter(args)` / `onLeave(retval)` for a native address. Here the target is HTTP traffic rather than a native function, and the arguments and return values are our own.

### Match gating {#match-gating}

- `hosts` is required. `methods` and `path` are optional; when absent they are unconstrained.
- Different fields are ANDed; candidates within one field are ORed.
- `path` is `exact` or `prefix`.
- Only matching traffic reaches the callbacks, so do not repeat the same conditions with a redundant `if` inside them.
- The current synthetic test and the existing `onRequest` / `onResponse` do not apply the manifest `match`, so keep the existing guards.
- Migration from subscriptions, ordering and count limits are TBD.

### Hook registration {#hook-registration}

A complete registration for `POST api.example.com/search`. `request` and `response` each have `onEnter` and `onLeave`.

```ts
Interceptor.attach(
  {
    hosts: ["api.example.com"],
    methods: ["POST"],
    path: { kind: "exact", value: "/search" },
  },
  {
    request: {
      onEnter(request) {
        // request.body is an illustrative UTF-8 decoded string (the object shape is TBD)
        rewriteJsonBody(request, (json) => {
          json.limit = 5
          json.locale = "ja-JP"
        })
      },
      onLeave(request) {
        // Runs after forwarding. The notification API is TBD, so this is a comment only
      },
    },
    response: {
      onEnter(response) {
        rewriteJsonBody(response, (json) => {
          json.maintenance = true
          json.message = "ただいまメンテナンス中です"
        })
      },
      onLeave(response) {
        // Runs after forwarding. The notification API is TBD, so this is a comment only
      },
    },
  },
)
```

The `request` / `response` arguments are traffic objects whose schema is TBD; the `body` above is an illustrative UTF-8 string. One plugin source may contain several `attach` calls (for example `POST /search` and `GET /status`), and the whole source is distributed as one plugin with one `id` and `version`. No ordering across the four hooks is promised.

### request.onEnter {#before-request}

`request.onEnter` runs before sending to the server and may edit the request. This example changes `limit`, adds `locale` and preserves other keys.

```javascript
onEnter(request) {
  rewriteJsonBody(request, (data) => {
    data.limit = 5
    data.locale = "ja-JP"
  })
}
```

Before:

```json
{
  "keyword": "coffee",
  "limit": 20
}
```

After:

```json
{
  "keyword": "coffee",
  "limit": 5,
  "locale": "ja-JP"
}
```

### request.onLeave {#after-request}

`request.onLeave` runs after forwarding to the server. Its argument is the request, not the response. Content already sent cannot change. The notification API is undecided.

```javascript
onLeave(request) {
  // Follow up on the request that was sent
}
```

### response.onEnter {#before-response}

`response.onEnter` runs after receiving the server response and before returning it to the original app. It may edit that response. Before and after `rewriteJsonBody` (other keys preserved):

```javascript
onEnter(response) {
  rewriteJsonBody(response, (data) => {
    data.maintenance = true
    data.message = "ただいまメンテナンス中です"
  })
}
```

Before:

```json
{
  "maintenance": false,
  "message": "通常営業中",
  "items": []
}
```

After:

```json
{
  "maintenance": true,
  "message": "ただいまメンテナンス中です",
  "items": []
}
```

### response.onLeave {#after-response}

`response.onLeave` runs after returning the response to the original app. It may follow up on the returned content, but cannot change it. The notification API is undecided.

```javascript
onLeave(response) {
  // Follow up on the response that was returned
}
```

### rewriteJsonBody {#rewrite-json-body}

`rewriteJsonBody(message, update)` is a built-in helper. Authors neither define nor import it, and it is used only in `onEnter`.

- Pass the hook argument (`request` or `response`) as `message`. The illustrative `message.body` is a decompressed, UTF-8 decoded string.
- `update(data)` synchronously mutates the parsed object. Its return value is ignored, except that returning any thenable (including a Promise) is an error without waiting for its outcome.
- The body is serialized only after the update succeeds.
- Missing or non-string bodies, invalid JSON, and parsed arrays, `null` or primitives skip `update` and leave the body unchanged.
- A callback exception, serialization failure or returned thenable preserves the original body and reports a helper error. Forwarding and UI behavior on overall hook failure are undecided.
- `rewriteJsonBody` itself returns `undefined`, with no success or skip status.
- Re-serialization may change JSON formatting (such as whitespace), and large integers may lose precision.

### Undecided behavior

Forwarding completion, hooks on partial or failed transfers, and handling of hook exceptions or timeouts are undecided. The peer receiving or processing the data is not guaranteed. Interceptor is expected to update `Content-Length` and recompress changed bodies, but streaming, large bodies and latency limits remain undecided.

### Manual execution {#manual}

Manual shortcut execution is a separate future feature, not a fifth traffic hook.
