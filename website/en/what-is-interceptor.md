---
title: What is Interceptor?
lang: en
---

<script setup>
import HookFlow from '../.vitepress/components/HookFlow.vue'
</script>

# What is Interceptor?

Interceptor is an app for inspecting HTTP and HTTPS traffic on iPhone and iPad. It sits between a client and a server, recording the requests sent and the responses returned. Use it to investigate API calls and their JSON data.

Inspecting HTTPS content requires certificate and target-host configuration. See [Getting started](getting-started.md) for setup steps.

## What are Plugins?

Plugins add JavaScript processing to traffic handled by Interceptor. Place a file at the location for its host, path and method, then change JSON in matching traffic or run processing after forwarding.

Package your processing as a plugin and load it in Interceptor. You can also sign plugins and share them through a repository.

::: info
An Interceptor build supporting schema 2 and live HTTP hooks is being prepared for distribution. Its version and download location will be announced when published. For now, try synthetic tests with the Rust simulator in [Authoring](authoring.md).
:::

## Use cases

- **Adjust requests**: For example, change `limit` from `50` to `5` in JSON sent to a search API. The server receives the modified value.
- **Change responses**: Add `maintenance: true` to JSON returned by an API to check how the client behaves when it receives that value.
- **Process matching traffic**: Apply changes only to a particular API. Interceptor checks the target conditions, so your JavaScript does not need to repeat them.

See [Write a plugin](authoring.md) for working JSON editing examples.

## How it works

Write your processing in functions called hooks. Requests and responses each have `onEnter` and `onLeave`. Use `onEnter` to edit JSON before forwarding, and the read-only `onLeave` to inspect the forwarded content.

<HookFlow locale="en" />

Plugins operate on traffic configured for Interceptor's proxy and approved by the user for plugin processing. Each plugin declares the data it reads and its JSON editing permissions. See the [API reference](api.md) for hook usage and traffic limits.

## Get started

- [Getting started](getting-started.md): Check compatible-build availability and the steps to follow after publication.
- [Write a plugin](authoring.md): Use TypeScript to change JSON and test the result.
- [Publishing](publishing.md): Sign your plugins and share them through a repository.
