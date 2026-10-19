---
title: Getting started
lang: en-US
---

<script setup>
import HookFlow from '../.vitepress/components/HookFlow.vue'
</script>

# Getting started

The schema 2 format and live HTTP hooks described here are under development. The four hooks require an Interceptor build supporting them. Import a plugin, test it with synthetic JSON, then approve its exact revision for live use. Plugin development also runs on Linux.

## Add the repository

Adding a repository displays its available plugins. Adding the URL does not run a script. Choose a plugin, import it disabled and test it.

Open **Settings → Plugins → + → Add Repository** and enter:

```text
%%REPOSITORY_URL%%
```

Before adding it, preview the repository name and script count. Signed repositories also show the signing-key fingerprint. After adding the repository, open each script's details to inspect all its source files and the manifest, which declares targets, permissions and other plugin metadata.

## Verifying trust

A fingerprint is a 64-character value identifying the publisher's signing key. Follow these steps to check whether the key shown in Interceptor belongs to the publisher you trust.

The SHA-256 fingerprint of this repository's Ed25519 public key:

```text
%%FINGERPRINT%%
```

1. Find the fingerprint in Interceptor's Add Repository preview.
2. Obtain a comparison fingerprint through a separate channel, such as an established contact for the publisher you already trust, independent of this site and feed.
3. Check that **all 64 characters match**. If you cannot obtain a comparison value, the values differ, or no valid fingerprint is shown, you cannot confirm the trusted publisher. Do not trust or add the repository.

The value on this page alone does not complete verification. This site and feed share GitHub administration and are not independent channels. This page does not provide a separate verification contact.

- The **package SHA-256** detects a mismatch between the index and a package. An unsigned server can replace both.
- The **public-key fingerprint** is a SHA-256 value identifying the signing key. A valid signature from a key you see for the first time does not prove who published it.
- **Ed25519 signatures** authenticate the index and the package hashes it lists against the signing key.

## Import and test

Synthetic tests execute input JSON without sending live traffic or webhooks.

1. Select a package and inspect all its source files and manifest.
2. Import it disabled.
3. Open the script and select a hook. Enter JSON containing traffic metadata as well as the HTTP body, then run the synthetic test.

For [Request summary](examples.md#request-summary), select `request.onEnter` and paste the full event below into the input JSON field.

<<< ../../fixtures/request-event.json{json}

The body preview should show `{"query":"x","limit":5}`. Changing the host to `other.example.com` produces no mutation because it does not match.

A synthetic test runs one phase. Selecting a leave phase does not send traffic; supply the data that would be visible after forwarding.

## Use on live traffic

For a schema 2 script, follow these steps. `api.example.com` is an illustrative host; use a plugin targeting an API you can access for a live test.

<HookFlow locale="en" />

1. Open **Settings → Capture Setup** and follow the certificate and VPN setup steps. Trusting the certificate lets Interceptor decrypt HTTPS for selected hosts.
2. Open **Settings → SSL Proxying List** and add the host shown in the script’s target conditions.
3. In **Settings → Plugins**, open the script and inspect its source, targets and grants. Choose **Live HTTP hooks → Approve This Revision…**, then confirm. A revision is the exact package containing all source files and the manifest shown.
4. Return to **Settings**, turn on **Status**, generate matching traffic and open the host's traffic from **Home** to inspect the forwarded JSON.

Approval lets the script read its declared traffic data and, when permitted, change JSON sent to a server or returned to a client.

Adding or revoking approval, or saving or deleting a schema 2 script, ends the current capture connection. Changes apply on the user's next explicit connection. Decryption-host and certificate-trust configuration is still required. Approving a plugin does not add decryption targets.

Importing or editing does not enable a revision. New or updated content needs fresh approval. Revoke approval or delete the script when no longer needed; revocation also ends an active connection.

Live JSON hooks have [format and size limits](api.md#execution-and-limits). External webhook delivery and manual execution from Shortcuts are not supported.
