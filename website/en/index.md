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

## What is Interceptor Plugin?

Interceptor is an app for inspecting network traffic between an app and a server. Interceptor Plugin adds custom processing written in JavaScript. Authors distribute a package containing the source and a manifest with its name, version and target conditions. This repository compiles TypeScript into JavaScript.

You can currently import plugins and try their processing with synthetic data. Returned webhook intents are displayed, never delivered. Automatic execution on live traffic and changes to traffic are not available yet. Start with the [current API](api.md#onrequest) and [synthetic preview samples](examples.md#request-summary).

## Build and publish

This site is the guide for users and authors of **%%REPOSITORY_NAME%%**. The repository URL is `%%REPOSITORY_URL%%`.

- [Getting started](getting-started.md): add, import and test
- [TypeScript authoring](authoring.md): build, test and bump versions
- [API reference](api.md): manifest fields, hooks, grants and bindings
- [Examples](examples.md): the real sources and manifests
- [Publishing](publishing.md): create and distribute your own repository
- [Development container](devcontainer.md): Linux development and publishing
