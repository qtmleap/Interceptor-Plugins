---
title: Home
lang: en-US
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: Try, build and publish plugins
  tagline: Interceptor Plugin adds custom JavaScript processing to Interceptor. You can currently try it with synthetic data and distribute signed packages.
  actions:
    - theme: brand
      text: Try with test data
      link: /en/getting-started
    - theme: alt
      text: Write a plugin
      link: /en/authoring
    - theme: alt
      text: Publish your repository
      link: /en/publishing
features:
  - title: Synthetic preview
    details: A synchronous v1 synthetic preview. It returns at most two webhook intents and never delivers them, attaches to live capture, or runs in the background.
    link: /en/api
  - title: Develop in TypeScript
    details: Edit src/*.ts and a manifest; the build type-checks and compiles readable JavaScript packages.
    link: /en/authoring
  - title: Signing and trust
    details: A package SHA-256 and the Ed25519 key fingerprint are different things. Compare the fingerprint through a channel you already trust.
    link: /en/getting-started#verifying-trust
  - title: Publish from the template
    details: Clone and run setup to configure a signing key, GitHub secret and Pages. After you push master, CI signs and publishes.
    link: /en/publishing
---

<script setup>
import HookFlow from '../.vitepress/components/HookFlow.vue'
</script>

## What is Interceptor Plugin?

Interceptor is an app for inspecting network traffic between an app and a server. Interceptor Plugin adds custom processing written in JavaScript. Authors distribute a package containing the source and a manifest with its name, version and target conditions. This repository compiles TypeScript into JavaScript.

You can currently import plugins and try their processing with synthetic data. Returned webhook intents are displayed, never delivered. Automatic execution on live traffic and changes to traffic are not available yet. Start with the [current API](api.md#onrequest) and [synthetic preview samples](examples.md#request-summary).

Future uses include changing a search limit in outgoing JSON, changing individual JSON response fields to test a maintenance screen, and following up on traffic with notifications. The HTTP Hook design below describes those uses.

## Traffic and Hook positions

**All four hooks in this diagram are unimplemented.** The current synthetic-test `onRequest` / `onResponse` functions do not run automatically along this traffic path.

<HookFlow locale="en" />

## When JavaScript runs

A request goes from the original app to the server; a response comes back. The design calls hooks only after Interceptor matches the host, path and method. Conditions and callbacks belong together in [`Interceptor.attach`](api.md#hook-registration), so the callback need not repeat those checks.

### 1. request.onEnter

Runs before sending the request to the server, while its content can still change. For example, change a search limit or language in a JSON body. See the [code and JSON before and after](api.md#before-request).

### 2. request.onLeave

Runs after forwarding the request, for follow-up work based on what was sent. Its argument is the request, not the server response. It cannot change content already sent. See the [callback example](api.md#after-request).

### 3. response.onEnter

Runs after receiving the server response and before returning it to the original app. A JSON replacement could help test a maintenance screen without changing the server. See the [code and JSON before and after](api.md#before-response).

### 4. response.onLeave

Runs after returning the response to the original app, for follow-up work such as identifying errors and notifying the user. It cannot change content already returned. See the [callback example](api.md#after-response).

The exact forwarding completion that triggers “after sending” or “after returning” is undecided; neither means the peer has received or processed the data. Notification APIs, streaming, compression, large bodies and latency limits are also undecided.

Running a chosen action from a Home Screen shortcut without waiting for traffic is another proposed feature. It is separate from the four traffic hooks and from today's synthetic tests. See [manual execution](api.md#manual).

## Build and publish

This site is the guide for users and authors of **%%REPOSITORY_NAME%%**. The repository URL is `%%REPOSITORY_URL%%`.

- [Getting started](getting-started.md): add, import and test
- [TypeScript authoring](authoring.md): build, test and bump versions
- [API reference](api.md): manifest fields, hooks, grants and bindings
- [Examples](examples.md): the real sources and manifests
- [Publishing](publishing.md): create and distribute your own repository
- [Development container](devcontainer.md): Linux development and its limits
