---
title: API reference
lang: en-US
---

# API reference

## Synchronous v1 synthetic preview

Hooks are called synchronously and return `{ actions: [...] }`. `actions` holds at most two webhook intents. They are displayed, never delivered; there is no live capture or background execution. The types aid authoring and are neither an input validator nor a permission grant: the app validates input and result limits at runtime. `read` declarations are validated and stored, but do not filter synthetic input.

## Type declarations

<<< ../../types/interceptor.d.ts{ts}

## Test input

`event` contains traffic data and `config` contains plugin settings. The simulator examples use these files:

`fixtures/request-event.json`:

<<< ../../fixtures/request-event.json{json}

`fixtures/config.json`:

<<< ../../fixtures/config.json{json}

The `run` command invokes the named function with these two JSON objects. `phase` is a value in the input; hook selection and event JSON are separate. Synthetic tests do not populate fields from a phase or filter them using manifest conditions. The supplied `event.request` and `event.response` data pass through unchanged.

`preview` is this sample's binding name. The test ID in `config.endpoints.preview` becomes the returned `endpointId`; synthetic tests need no real delivery endpoint. In the app, the script detail test section lets you edit the hook, event JSON and configuration JSON.

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
