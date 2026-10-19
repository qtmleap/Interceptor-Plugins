---
title: Home
lang: en
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: Run JavaScript around HTTP traffic
  tagline: Interceptor Plugin adds JavaScript processing to HTTP traffic. Package JSON edits before forwarding and callbacks after successful forwarding into a plugin.
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
    details: Choose the host, path and method to process.
    link: /en/api
  - title: Edit JSON directly
    details: Change request or response JSON before forwarding.
    link: /en/authoring
  - title: Develop and publish on Linux
    details: Develop with Bun and the Rust simulator. Signing does not require Xcode.
    link: /en/devcontainer
---

<script setup>
import HookFlow from '../.vitepress/components/HookFlow.vue'
</script>

## When JavaScript runs

Use `onEnter` before forwarding and `onLeave` after successful local forwarding.

<HookFlow locale="en" />

See [Authoring](authoring.md) for code examples and the [API reference](api.md) for each hook's contract.
