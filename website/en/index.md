---
title: Home
lang: en
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: Run JavaScript around HTTP traffic
  tagline: Interceptor Plugin adds your own processing to matching requests and responses. Edit JSON before forwarding, or run a callback after forwarding succeeds.
  actions:
    - theme: brand
      text: Write a plugin
      link: /en/authoring
    - theme: alt
      text: Try it in the app
      link: /en/getting-started
    - theme: alt
      text: Publish
      link: /en/publishing
features:
  - title: Match the traffic you need
    details: Choose the host, path and method. Only matching traffic reaches your callbacks, so each function does not need to repeat those checks.
    link: /en/api
  - title: Edit JSON directly
    details: request.onEnter can edit JSON going to the server. response.onEnter can edit JSON going back to the client.
    link: /en/authoring
  - title: Develop and publish on Linux
    details: Build TypeScript with Bun and check syntax and execution with the Rust simulator. Package signing does not require Xcode.
    link: /en/devcontainer
---

<script setup>
import HookFlow from '../.vitepress/components/HookFlow.vue'
</script>

## What is an Interceptor Plugin?

Interceptor inspects traffic between a client and a server. Plugins add JavaScript processing to that traffic: change a search limit, add a field to a JSON response, or build a result from the forwarded data.

Authors package source and a manifest together. The manifest declares the target traffic and the data the plugin may read or change. Users inspect these declarations and approve an exact revision before using it on live traffic.

## When JavaScript runs

Requests and responses each have an `onEnter` and an `onLeave` callback.

<HookFlow locale="en" />

### request.onEnter

Runs before forwarding the client's request to the server. For example, `request.body.limit = 5` changes the JSON field before sending it.

### request.onLeave

Runs after the request was successfully forwarded locally. Use the forwarded data to build a result. Traffic is read-only at this point.

### response.onEnter

Runs before returning the server's response to the client. For example, `response.body.maintenance = true` adds a JSON field.

### response.onLeave

Runs after the response was successfully forwarded locally. Use the returned data to build a result. Traffic is read-only at this point.

See the [API](api.md#request-onenter) for callbacks and [Authoring](authoring.md#edit-json) for before-and-after JSON. Webhook intents appear in synthetic-test results. Live processing does not save or deliver returned intents.

## Create and publish

This is the guide for **%%REPOSITORY_NAME%%**. Its feed URL is `%%REPOSITORY_URL%%`.

- [Getting started](getting-started.md): import, test and approve a revision
- [Authoring](authoring.md): TypeScript, JSON edits and the simulator
- [API](api.md): four hooks, matching and permissions
- [Examples](examples.md): source and manifests
- [Publishing](publishing.md): sign and distribute packages
- [Dev container](devcontainer.md): develop on Linux
