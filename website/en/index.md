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
      text: What is Interceptor?
      link: /en/what-is-interceptor
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
      src: /icons/check.svg
      alt: ""
      wrap: true
      width: 24
      height: 24
    title: Try it with test data
    details: Use sample requests and responses to check JSON changes and matching conditions. Try your plugin before applying it to live traffic.
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
