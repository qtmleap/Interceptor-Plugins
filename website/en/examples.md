---
title: Examples
lang: en
---

<script setup>
import HookFlow from '../.vitepress/components/HookFlow.vue'
</script>

# Examples

Each example contains an authored TypeScript file and a `plugin.json` for metadata and permissions. Both use the schema 2 format under development. Inputs and expectations are in `fixtures/cases.json`. Returned webhook intents appear in synthetic-test results. Live processing does not save or deliver them.

<HookFlow locale="en" />

## Request summary {#request-summary}

Targets `POST api.example.com/search`. `request.onEnter` changes `limit` to `5`; `response.onEnter` adds `maintenance: true`. The leave callbacks build intents from the forwarded data.

`plugins/request-summary/hooks/api.example.com/search/POST.ts`

<<< ../../plugins/request-summary/hooks/api.example.com/search/POST.ts{ts}

<<< ../../plugins/request-summary/plugin.json{json}

This file defines all four callbacks in one `Interceptor.attach` call. To handle another API, add a file at its corresponding location under the same plugin’s `hooks/` directory. The build generates the target conditions and file references.

## Server error filter {#server-error-filter}

Handles responses to `GET https://example.com/`. The file location selects the host, path and method; the callbacks check for a 5xx status. Only those responses receive `maintenance: true` before forwarding and produce a host/status test action afterward.

`plugins/server-error-filter/hooks/example.com/GET.ts`

<<< ../../plugins/server-error-filter/hooks/example.com/GET.ts{ts}

<<< ../../plugins/server-error-filter/plugin.json{json}
