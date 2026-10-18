# Maintaining and publishing

The repository maintainer is responsible for feed expiry, scheduled-workflow state, signing-key backup and incident response. This repository does not create an external monitor or a separate cron service.

## Local checks

Run `bun install --frozen-lockfile --ignore-scripts` then `bun run check` with Xcode 27.0 (Swift 6.4), the Bun version in `.bun-version`, Python 3 and Git. CI installs the exact TypeScript compiler from `bun.lock`. This is also the complete CI command. CI selects the hosted `xcode-27` image and explicitly sets `DEVELOPER_DIR` to Xcode 27.0.0. The older default Swift 6.1 on `macos-15` cannot compile the pinned library's actor-isolation code; checks fail early on unsupported compilers. The library's macOS 14 deployment target is unchanged. The upstream runtime is a sparse checkout at the full SHA in `repository-config.json`; a different or modified cache is refused. If updating the pin deliberately, preserve or remove only your own `.tools/interceptor` cache, review the new source, and run all checks again.

The checks exercise real QuickJS outputs, generation determinism, a known wrong event shape, signed metadata, package/payload tampering, wrong keys and bounded HTTPS behavior. Keys for these tests live in a temporary directory outside Git and the published site, and are removed on exit. Test output is in `build/evidence/`; generated packages are in `build/site/`. Neither belongs in Git.

## Set up your own signed feed

For a fresh template, prefer `bun run setup` as described in the README. It configures Pages, a restricted environment and your own signing secret using your existing GitHub CLI administrator authentication. It keeps a private retry checkpoint with the key outside the checkout, and does not commit, push or deploy. Back up that directory and rerun the command after an interrupted setup; do not delete the checkpoint or regenerate IDs to fix a transient error. Unknown existing secrets and changed configuration require manual investigation. If an interrupted secret upload leaves a visible secret without confirmed checkpoint metadata, setup stops without overwriting it. Keep the local key/checkpoint, inspect the environment secret as its maintainer, resolve that unconfirmed remote secret manually, then rerun setup. The same IDs and key are reused; do not regenerate them. An environment created by an older pre-setup workflow may need its master-only policy configured manually; the current secret-free preflight prevents that automatic unprotected-environment creation. Secret readback checks metadata only; successful signed live verification confirms the effective key.

The following manual procedure remains available for existing feeds. Generate your own key with the pinned publisher and use `tools/configure.py` only for a new, unpublished copy: every call allocates new UUIDs. Keep your own repository/plugin UUIDs and URL stable after publication. The shared `tools/reserved.json` retains official current and retired identities. A template that still uses an official identity is rejected before signing.

1. Enable GitHub Pages with **GitHub Actions** as the build source.
2. Create the `github-pages` environment and restrict its deployment branch policy to the branch named `master`. Do this before storing the signing secret or triggering a release. Existing organization rules remain applicable; this setup does not introduce another required human approval for each renewal.
3. Store a base64 encoding of your raw 32-byte Ed25519 key in the **environment secret** named `INTERCEPTOR_REPOSITORY_KEY_B64`. Do not create it as a repository-wide secret. Never print it or put it in a workflow file.

   For example, pipe it directly to GitHub CLI; substitute your key and repository:

   ```sh
   python3 -c 'import base64,sys; from pathlib import Path; sys.stdout.write(base64.b64encode(Path(sys.argv[1]).read_bytes()).decode())' \
     ~/.config/interceptor/my-plugins.key |
     gh secret set INTERCEPTOR_REPOSITORY_KEY_B64 --env github-pages --repo YOUR_NAME/YOUR_REPO
   ```

4. Commit the **public** fingerprint in `repository-config.json` and the README, and distribute it through an independently trusted channel. Keep an offline backup of the private key. A template does not inherit the official environment or its secret.
5. Push tested source to `master`. The publishing workflow checks the configured identity, runs the full suite without the official key, restores the environment secret to a 0600 file under `RUNNER_TEMP`, signs, deploys only `build/site/`, and removes that file on every outcome.

PR checks have read-only repository permissions and no signing environment. The publish workflow is limited to `master`; its environment branch restriction is a second boundary. It fails when the secret is missing or its fingerprint differs from the config, instead of falling back to an unsigned official feed.

## Sequence, expiry and verification

The publisher creates metadata valid for 30 days. The workflow runs on master pushes, manual dispatch and weekly on Monday at 02:17 UTC (11:17 Japan time). The entire publishing workflow shares one concurrency group with `cancel-in-progress: false`. A stale master SHA is a failure; confirm the newer master run completes or dispatch it manually.

`tools/publish.sh` reads the prior feed over HTTPS, refusing redirects and any non-200 status except an initial 404. It authenticates the prior index against the configured key and UUID, even when expired, before using its sequence. This expiry exception is only for renewal preflight. App import and final live verification still enforce current time.

The new sequence is current Unix milliseconds and must strictly increase. It is not an arbitrary workflow input. Clock rollback or invalid metadata stops publication. After deployment, the app's own `RepositoryClient` fetches the exact sequence, checks the signature/fingerprint and at least 14 days of remaining validity, then fetches and checks every package. Bounded retries only read; they do not re-sign or re-deploy.

GitHub disables public-repository schedules after 60 days without repository activity, and template schedules are disabled initially. Weekly jobs do not guarantee perpetual availability. Check workflow state and feed expiry weekly; failure notifications do not cover a disabled job that never runs. To recover, re-enable **Publish signed repository**, run it manually on `master`, and wait for both deployment and live verification. Installed revisions remain offline; expiry affects refresh/import.

## Verify a deployed run manually

Build using `tools/check.sh`, then obtain the successful run's sequence from its logs and run:

```sh
verifier="$(swift build --package-path tools/Verifier --configuration release --show-bin-path)/interceptor-samples-check"
"$verifier" verify-live "$PWD" EXPECTED_SEQUENCE
```

A different sequence, UUID, key, expired index, bad package hash, redirect or transport error is a failure. A Pages upload receipt alone does not prove this verification succeeded. Inspect existing run/deployment state before repeating an uncertain write.

## Key loss or compromise

Only maintainers act on the signing key. If it may be compromised, stop the publishing workflow, disable its secret and stop the old feed. This cannot remotely revoke installed revisions or users' pinned keys.

Create a new key, repository UUID and URL (a new feed directory is sufficient). Review the updated config, README and reserved identities together; retain the old IDs and fingerprints in `tools/reserved.json`. Do not redirect the old URL or silently replace a trusted key. Users must explicitly register the new URL and independently check/pin its fingerprint.

For the official repository, maintainers announce the incident and new fingerprint through the existing qleap.jp official site as well as GitHub. This is a human incident-response procedure, not an automated message sender or a claim that the README is an independent trust channel.

## Provenance

The published packages contain only this repository's manifests and JavaScript. Sources are TypeScript in `src/`; `tools/build.py` always compiles them independently to readable global-script JavaScript in `build/scripts/` before packaging. Their SHA-256 values cover exact UTF-8 package bytes including the emitted JavaScript, rather than the TypeScript text. The pinned upstream publisher supplies the v1 index and Ed25519 signature; no separate crypto implementation is maintained here. Toolchain identity is recorded under `build/evidence/toolchain.txt` for each run.

References: [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), [workflow enable/disable behavior](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows).
