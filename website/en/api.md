---
title: API reference
lang: en-US
---

# API reference

## Synchronous v1 synthetic preview

Hooks are called synchronously and return `{ actions: [...] }`. `actions` holds at most two webhook intents. They are displayed, never delivered; there is no live capture or background execution. The types aid authoring and are neither an input validator nor a permission grant: the app validates limits and permissions at runtime.

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

## Hooks

- `onRequest(event, config)`: request phases
- `onResponse(event, config)`: response phases

Optional properties of `event.request` and `event.response` depend on the input and the read grants. Always check that they exist.

## Read grants

Declare only what you need under `read`:

- `metadata`: such as `method`, `host`, `path`, `status`
- `headers`: the header names to read
- `queryKeys`: the query keys to read
- `body.mode`: `none` reads no body

## Endpoint bindings

A name declared in `endpointBindings` is resolved as `config.endpoints[name]`, giving the destination ID. Tests use the values in `fixtures/config.json`. Put that value in the intent's `endpointId`, and handle the `undefined` case.
