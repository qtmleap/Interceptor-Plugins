---
title: Home
lang: en
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: Frida-like hooks for HTTP traffic
  tagline: Change request and response JSON or run your own JavaScript as traffic passes through Interceptor.
  image:
    src: /images/interceptor.png
    alt: Interceptor
  actions:
    - theme: brand
      text: Write a plugin
      link: /en/authoring
    - theme: alt
      text: Try it in the app
      link: /en/getting-started
features:
  - icon:
      src: /icons/filter.svg
      alt: ""
      wrap: true
      width: 24
      height: 24
    title: Match the traffic you need
    details: Choose a host, path and method. Hooks run only for matching traffic, so you can focus on the processing instead of repeating those checks in JavaScript.
    link: /en/api
  - icon:
      src: /icons/json.svg
      alt: ""
      wrap: true
      width: 24
      height: 24
    title: Edit JSON directly
    details: Read and change request and response JSON directly in JavaScript. Replace values or add fields in the data actually sent to the server or client.
    link: /en/authoring
  - icon:
      src: /icons/terminal.svg
      alt: ""
      wrap: true
      width: 24
      height: 24
    title: Develop on Linux
    details: Use Bun and the Rust simulator to check syntax and run hooks against test data. Develop and test plugins on Linux without macOS or Xcode.
    link: /en/authoring
  - icon:
      src: /icons/package.svg
      alt: ""
      wrap: true
      width: 24
      height: 24
    title: Sign and share
    details: Sign your plugins and share them through a repository. Users add its URL to Interceptor, then choose the plugins they want to load.
    link: /en/publishing
---
