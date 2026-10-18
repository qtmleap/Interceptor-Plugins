---
title: Getting started
lang: en-US
---

# Getting started

You need **Interceptor 1.1.0 or later** with the Plugins preview. A plugin is a script that processes supplied traffic information. The current preview lets you run the samples with test data and inspect the result; it does not send or receive live traffic.

## Add the repository

Adding a repository displays its available plugins. Adding the URL does not run a script. Choose a plugin, import it disabled and test it.

Open **Settings → Plugins → + → Add Repository** and enter:

```text
%%REPOSITORY_URL%%
```

Before adding it, preview the repository name and script count. Signed repositories also show the signing-key fingerprint. After adding the repository, open each script's details to inspect its source and manifest.

## Verifying trust

A fingerprint is a 64-character value identifying the publisher's signing key. Compare the **entire value** with one obtained through a separate channel you trust. If it differs, or no valid value appears below, you cannot confirm the source and should not trust it.

The SHA-256 fingerprint of this repository's Ed25519 public key:

```text
%%FINGERPRINT%%
```

- The **package SHA-256** detects a mismatch between the index and a package. An unsigned server can replace both.
- The **public-key fingerprint** is a SHA-256 value identifying the signing key. A valid signature from a key you see for the first time does not prove who published it.
- **Ed25519 signatures** authenticate the index and the package hashes it lists against the signing key.
- This site and the feed share GitHub administration, so this page alone is not an independent trust channel. Compare the **full fingerprint** through a channel you already trust before pinning it.

## Import and test

The test shows what a script returns for the supplied input. It sends nothing to external servers.

1. Choose a package from the list and inspect its source.
2. Select **Import Disabled** to store it without enabling it.
3. Open the imported script, choose its hook, and select **Run Synthetic Test** to run the test data.

| Sample | Hook | Default displayed JSON payload |
|---|---|---|
| Request summary | Request | `{"summary":"GET example.com/synthetic"}` |
| Server error filter | Response | `{"host":"example.com","status":503}` |

For the no-action case, change the response status in the test input to `200`. A request-only script does not define `onResponse`, and vice versa, so choose the hook that matches the script.

## What the preview does

This is a synchronous v1 **synthetic preview**. It runs explicit input and displays the returned webhook intents.

- At most two intents are returned.
- Nothing is **delivered** to a webhook.
- It does not attach to live capture.
- It does not run in the background.
- Imports are stored disabled. The samples request no body, header or query values.

If the result matches the table, importing and testing the sample is complete. See [Examples](examples.md) to try another sample. To create your own plugin, continue with [TypeScript authoring](authoring.md).
