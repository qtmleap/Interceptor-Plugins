---
title: Examples
lang: en
---

<script setup>
import HookFlow from '../.vitepress/components/HookFlow.vue'
</script>

# Examples

Each example contains an authored TypeScript file and a `plugin.json` for metadata and permissions. Both use the schema 2 format under development. Inputs and expectations are in `fixtures/cases.json`. The `webhook` actions below are an output format for synthetic tests. They do not send HTTP requests, and live processing does not save or deliver them.

<HookFlow locale="en" />

## Request summary {#request-summary}

Request summary combines JSON changes with test summary actions built from forwarded data. It targets `POST api.example.com/search`. `request.onEnter` changes `limit` to `5`; `response.onEnter` adds `maintenance: true`. The leave callbacks build intents from the forwarded data.

`plugins/request-summary/hooks/api.example.com/search/POST.ts`

<<< ../../plugins/request-summary/hooks/api.example.com/search/POST.ts{ts}

<<< ../../plugins/request-summary/plugin.json{json}

This file defines all four callbacks in one `Interceptor.attach` call. To handle another API, add a file at its corresponding location under the same plugin’s `hooks/` directory. The build generates the target conditions and file references.

## Server error filter {#server-error-filter}

In Server error filter, “filter” means processing only 5xx responses; it does not remove errors or block traffic. It handles responses to `GET https://example.com/`. The file location selects the host, path and method; the callbacks check for a 5xx status. Only those responses receive `maintenance: true` before forwarding and produce a host/status test action afterward.

`plugins/server-error-filter/hooks/example.com/GET.ts`

<<< ../../plugins/server-error-filter/hooks/example.com/GET.ts{ts}

<<< ../../plugins/server-error-filter/plugin.json{json}

## Outbound example {#outbound-example}

This development example lives under `fixtures/` and is not a published default plugin. It handles a `200` response to `GET https://interceptor-traffic-fixture.lemonandchan.workers.dev/auth/credentials`, reading `accessToken` from JSON and the granted `set-cookie` header. `response.onLeave` records a `bearer` send to `/auth/bearer` and a `cookie` send to `/auth/cookie`. Both destinations are fixed in `outbound`.

The public test API returns `accessToken: "interceptor-test-token"` and `fixture_session=dummy-session-not-a-secret`. The example extracts the first Cookie pair and omits `Set-Cookie` attributes such as `Path`. Running it in the simulator records intents without sending secondary requests.

`fixtures/outbound-example/hooks/interceptor-traffic-fixture.lemonandchan.workers.dev/auth/credentials/GET.ts`

<<< ../../fixtures/outbound-example/hooks/interceptor-traffic-fixture.lemonandchan.workers.dev/auth/credentials/GET.ts{ts}

<<< ../../fixtures/outbound-example/plugin.json{json}
