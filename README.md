# Interceptor Plugins

[日本語](README.ja.md)

Official examples and a repository template for Interceptor's JavaScript preview feature. Edit ordinary `.js` files and manifests, test them with the app's own QuickJS engine, and publish signed v1 packages over HTTPS.

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

Requires macOS 14+, Swift 6+, Python 3 and Git. From this checkout:

```sh
tools/check.sh
```

The command fetches the pinned public Interceptor source, builds its publisher and QuickJS driver, checks deterministic package bytes, runs request/response fixtures, and checks signed metadata and byte-tampering failures with a temporary test key. It never uses the official signing key or publishes anything.

Sources live in `scripts/` and `manifests/`; expected input and output live in `fixtures/`. `build/site/` is generated and ignored. The upstream runtime revision is recorded in `repository-config.json`; no QuickJS or crypto implementation is copied here.

## Make your own repository

1. Select **Use this template**, choose your own repository name, and clone it. The default config belongs to the official feed; change it before signed deployment.
2. Generate your own signing key outside the checkout and any web directory. Keep a secure backup. Never commit it.

   ```sh
   tools/bootstrap.sh
   mkdir -p ~/.config/interceptor
   swift run --package-path .tools/interceptor/Packages/InterceptorAutomation \
     interceptor-repository keygen ~/.config/interceptor/my-plugins.key
   ```

   The command prints the public-key fingerprint, not the private key.

3. Configure your identity, substituting your repository, URL and the fingerprint printed above. This allocates new repository and plugin UUIDs.

   ```sh
   python3 tools/configure.py --root . \
     --repository YOUR_NAME/YOUR_REPO --name "My plugins" \
     --url https://YOUR_NAME.github.io/YOUR_REPO/repository.json \
     --fingerprint YOUR_64_HEX_FINGERPRINT
   ```

4. Edit a script and its manifest together, update its version, and add a fixture with literal expected output. Keep the v1 package and action contracts. Run `tools/check.sh`.
5. Follow [Maintaining and publishing](docs/maintaining.md) to create a main-restricted signing environment, store your own secret, enable Pages, and verify the live URL. Publish the fingerprint through a separate trusted channel.

An unsigned local feed is supported for development and requires the app's unverified-repository acknowledgment. SHA-256 detects package differences against an index; an unsigned server can replace both. Official deployment fails if its signing key is absent.

## Operations

Generated metadata expires after 30 days. Pushes to `main`, manual runs and the weekly publishing workflow renew it. GitHub can disable schedules after 60 days without repository activity; maintainers must check workflow state and feed expiry. See [recovery, key handling and verification](docs/maintaining.md).

MIT licensed. Interceptor's reused tooling and its vendored QuickJS retain their upstream licenses.
