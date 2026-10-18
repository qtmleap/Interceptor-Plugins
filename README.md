# Interceptor Plugins

[日本語](README.ja.md)

Official examples and a repository template for Interceptor's JavaScript preview feature. Author `.ts` files and manifests, compile readable JavaScript, test it with the app's own QuickJS engine, and publish signed v1 packages over HTTPS.

## Add the official repository

Use Interceptor **1.1.0 or later with the Plugins preview**. In **Settings → Plugins → + → Add Repository**, enter:

```text
https://qtmleap.github.io/Interceptor-Plugins/repository.json
```

Preview the source, declarations and signing-key fingerprint before adding. A signature from a key seen for the first time does not automatically authenticate its publisher. Compare the full fingerprint through a channel you already trust before pinning it. The README and Pages feed share GitHub administration, so this page alone is not an independent trust channel.

Official public-key fingerprint: **b29b13755f2df72858c5d14ea7c1b293fa379b9ad3ea2f86f016dfa0735cd96a**

Choose a package, inspect its source, and select **Import Disabled**. Open the imported script, choose the hook below, then **Run Synthetic Test**.

| Sample | Hook | Default displayed JSON payload |
|---|---|---|
| Request summary | Request | `{"summary":"GET example.com/synthetic"}` |
| Server error filter | Response | `{"host":"example.com","status":503}` |

For the filter's no-action case, change the response status in the test input to `200`. Choose the matching hook: a request-only script does not define `onResponse`, and vice versa.

This preview runs explicit synthetic input and displays the returned intent. It does not connect these samples to captured traffic, run them in the background, or deliver webhooks. Imports are stored disabled. No request body, headers or query values are requested by these samples.

## Run the checks

The checks use Xcode 27.0 (Swift 6.4), Node.js (the version in `.node-version`), Python 3 and Git on a compatible Mac. The reused Swift package keeps its macOS 14 deployment target; older default Swift compilers cannot build the pinned automation library. From this checkout:

```sh
npm ci --ignore-scripts
npm run check
```

The command fetches the pinned public Interceptor source, builds its publisher and QuickJS driver, checks deterministic package bytes, runs request/response fixtures, and checks signed metadata and byte-tampering failures with a temporary test key. It never uses the official signing key or publishes anything.

Canonical sources live in `src/*.ts` and `manifests/`; expected input and output live in `fixtures/`. Packaging always type-checks and compiles from source. `build/scripts/` and `build/site/` are generated and ignored. See [TypeScript authoring](docs/authoring.md) for hook types and host limits. The upstream runtime revision is recorded in `repository-config.json`; no QuickJS or crypto implementation is copied here.

## Make your own repository

1. Select **Use this template**, create a **public** repository with default branch **master**, and clone your copy. If cloning directly, set `origin` to your own GitHub repository before setup.
2. On a compatible Mac with GitHub CLI authenticated as a repository administrator, run:

   ```sh
   npm ci --ignore-scripts
   npm run setup
   npm run check
   ```

   Setup allocates new repository/plugin IDs, creates your signing key outside Git, stores its environment secret behind a master-only deployment policy, sets Pages to use Actions and enables publishing. It preserves existing protections and refuses unknown keys/secrets or an official checkout. Keep a secure backup of `~/.config/interceptor/repositories/OWNER--NAME/`: it holds your private key and retry checkpoint. Re-running setup resumes the same identity and key. No commit, push or deployment is performed by setup.
3. Edit `src/NAME.ts`, its manifest and fixtures together. Commit your **public configuration**, TypeScript, manifests and tests, then push `master`. CI compiles, checks real QuickJS outputs, generates package SHA-256 hashes, signs and publishes automatically. No manual signing commands are needed for each release.
4. Wait for **Publish signed repository** to pass its live verification. Register the printed `https://OWNER.github.io/REPO/repository.json` URL in Interceptor. Setup's URL is a future address until deployment succeeds. Share the public fingerprint through an independently trusted channel; a valid signature alone does not prove publisher identity.

The first setup needs GitHub administration permission to configure Pages, the deployment environment and its secret; the workflow's ordinary token does not bootstrap these credentials. Organization restrictions may require a maintainer to adjust settings. Existing repositories can use the [manual setup and recovery instructions](docs/maintaining.md).

An unsigned local feed is supported for development and requires the app's unverified-repository acknowledgment. SHA-256 detects package differences against an index; an unsigned server can replace both. Official deployment fails if its signing key is absent.

## Operations

Generated metadata expires after 30 days. Pushes to `master`, manual runs and the weekly publishing workflow renew it. GitHub can disable schedules after 60 days without repository activity; maintainers must check workflow state and feed expiry. See [recovery, key handling and verification](docs/maintaining.md).

MIT licensed. Interceptor's reused tooling and its vendored QuickJS retain their upstream licenses.
