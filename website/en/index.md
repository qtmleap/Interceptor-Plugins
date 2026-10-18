---
title: Home
lang: en-US
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: Try, build and publish plugins
  tagline: Try the samples with test data in Interceptor, or write your own TypeScript plugin and distribute signed packages.
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

This site is the guide for users and authors of **%%REPOSITORY_NAME%%**. The repository URL is `%%REPOSITORY_URL%%`.

- [Getting started](getting-started.md): add, import and test
- [TypeScript authoring](authoring.md): build, test and bump versions
- [API reference](api.md): manifest fields, hooks, grants and bindings
- [Examples](examples.md): the real sources and manifests
- [Publishing](publishing.md): create and distribute your own repository
- [Development container](devcontainer.md): Linux development and its limits
