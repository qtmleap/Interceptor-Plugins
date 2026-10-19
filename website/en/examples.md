---
title: Examples
lang: en-US
---

# Examples

"Request summary" and "Server error filter" are existing, real samples from the repository. The future design at the end is unimplemented and is not presented as executable.

Long code blocks scroll horizontally. Use the code block’s copy control to copy the entire source.

## Request summary

On a completed `GET example.com` request, returns a `GET example.com/path` summary.

<<< ../../src/request-summary.ts{ts}

<<< ../../manifests/request-summary.json{json}

## Server error filter

Only for 5xx responses from `example.com`, returns the host and status.

<<< ../../src/server-error-filter.ts{ts}

<<< ../../manifests/server-error-filter.json{json}

Neither reads a body, headers or query values (`body.mode` is `none`), and both use only the `preview` binding. The synthetic test does not apply manifest filters, so the sources also check method, host and status.

## Future HTTP Hook design (unimplemented) {#future-http-hooks}

::: info Unimplemented API
This is an unimplemented design example. The current runtime has neither `Interceptor.attach` nor `rewriteJsonBody`, so it will not run in synthetic tests. `rewriteJsonBody` is designed as a runtime built-in; authors do not define or import it.
:::

A design example with two `attach` calls, `POST /search` and `GET /status`, in one plugin source. Place the `Interceptor.attach` calls at the top level of the same source. The whole plugin has a single `id` and `version`. See [HTTP Hook design](api.md#http-hooks).

```javascript
Interceptor.attach({
  hosts: ["api.example.com"],
  methods: ["POST"],
  path: { kind: "exact", value: "/search" }
}, {
  request: {
    onEnter(request) {
      rewriteJsonBody(request, (data) => {
        data.limit = 5;
        data.locale = "ja-JP";
      });
    },
    onLeave(request) {
      // Follow up after sending the search request
    }
  },
  response: {
    onEnter(response) {
      // Process search results before returning them to the original app
    },
    onLeave(response) {
      // Follow up after returning search results
    }
  }
});

Interceptor.attach({
  hosts: ["api.example.com"],
  methods: ["GET"],
  path: { kind: "exact", value: "/status" }
}, {
  request: {
    onEnter(request) {
      // Process the status request before sending it
    },
    onLeave(request) {
      // Follow up after sending the status request
    }
  },
  response: {
    onEnter(response) {
      rewriteJsonBody(response, (data) => {
        data.maintenance = true;
        data.message = "ただいまメンテナンス中です";
      });
    },
    onLeave(response) {
      // Follow up after returning the status response
    }
  }
});
```
