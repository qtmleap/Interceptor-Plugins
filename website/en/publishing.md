---
title: Publishing
lang: en-US
---

# Publishing

How to create and distribute your own repository.

## Steps

1. Open the [GitHub template repository](https://github.com/qtmleap/Interceptor-Plugins), choose **Use this template**, create a **Public** repository with default branch **master**, and clone your new repository. If you clone directly, set `origin` to your own GitHub repository first.
2. On Linux or macOS with GitHub CLI signed in as a repository administrator, run:

   ```sh
   bun install --frozen-lockfile --ignore-scripts
   bun run setup
   bun run check
   ```

   Setup configures new IDs, a signing key (kept outside Git), a master-only environment secret and Pages (Actions). It does not commit, push or deploy. Your private key and retry checkpoint live in `~/.config/interceptor/repositories/OWNER--NAME/`; back it up.
3. Edit `src/NAME.ts`, the manifest and fixtures, commit them with your public configuration, and push `master`.
4. When **Publish signed repository** passes its live verification, register the printed `https://OWNER.github.io/REPO/repository.json` URL in the app. Until then it is only the intended address.

Setup writes repository and plugin IDs, the feed URL and public-key fingerprint into configuration files. Commit that public configuration too. Organization permissions and any additional protections still apply.

After an interruption, keep the private key and checkpoint and rerun `bun run setup`. It resumes with the same IDs and key; do not delete the checkpoint or regenerate a key to investigate a failure. It refuses to overwrite an existing key or secret whose ownership it cannot establish. See the maintainer guide below for recovery.

The repository's distribution data is called a feed. Unsigned local feeds are available for development and require the app's unverified-repository acknowledgment. Official signed publication never falls back to unsigned metadata.

## Signing and publishing with GitHub Actions

CI on master type-checks, compiles, tests with real QuickJS, generates SHA-256 hashes, signs, and publishes one GitHub Pages deployment. This site is part of that same deployment; `repository.json` and `plugins` belong to the signed feed. No manual signing is needed per release.

Generated metadata expires after 30 days and is renewed by master pushes, manual runs and the weekly workflow. GitHub can disable schedules after 60 days without activity, so maintainers must check workflow state and expiry.

## Trust

Share the public fingerprint through an independently trusted channel too. A valid signature alone does not prove the publisher's identity.

## For maintainers

For key handling, recovery and post-deployment verification, see the [maintenance and publishing guide (docs/maintaining.md)](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/docs/maintaining.md).

## Signing

Bun's cryptography support handles Ed25519. Private keys remain raw 32-byte seeds; the app's signature format and public-key fingerprints stay compatible. Setup, checks and signed-feed generation run on Linux. Xcode and Apple code signing are not required.

The publishing workflow also runs on Ubuntu. It restores the environment signing secret only after all checks pass, verifies the published files and removes its restored key on every outcome.
