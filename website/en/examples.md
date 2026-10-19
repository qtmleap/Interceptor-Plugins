---
title: Examples
lang: en
---

<script setup>
import HookFlow from '../.vitepress/components/HookFlow.vue'
</script>

# Examples

Both examples use schema 2. Inputs and expectations are in `fixtures/cases.json`. Returned webhook intents appear in synthetic-test results. Live processing does not save or deliver them.

<HookFlow locale="en" />

## Request summary {#request-summary}

Targets `POST api.example.com/search`. `request.onEnter` changes `limit` to `5`; `response.onEnter` adds `maintenance: true`. The leave callbacks build intents from the forwarded data.

<<< ../../src/request-summary.ts{ts}

<<< ../../manifests/request-summary.json{json}

Place all four callbacks in one `attach`, or arrange calls by processing task. Each match must equal a manifest entry.

## Server error filter {#server-error-filter}

Targets 5xx responses from `example.com`. Matching checks the status before callbacks, so the callback needs no duplicate status guard. It adds `maintenance: true` before forwarding and returns a host/status intent afterward.

<<< ../../src/server-error-filter.ts{ts}

<<< ../../manifests/server-error-filter.json{json}
