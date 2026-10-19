# Official Plugin Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the official signed Interceptor sample repository and a reusable creation template, then verify the live feed with the app's own libraries.

**Architecture:** Editable JS plus separate manifests produce deterministic v1 packages. A pinned checkout supplies the publisher, validator, repository client and QuickJS; a small local Swift package drives sample and feed verification. GitHub Pages serves only generated artifacts.

**Tech Stack:** Python 3 standard library, Swift 6, AutomationCore/Runtime/Repository, GitHub Actions and Pages.

**Spec:** ../specs/2026-10-17-official-plugin-repository-design.md (approved; user waived further approval gates).

## Global Constraints

- macOS 14+ and Swift 6+; initial CI image macos-15; record toolchain versions.
- Pin qtmleap/Interceptor at 50307c2af38be2524f988e3d1d8a950973d63fd5; do not copy QuickJS or crypto code.
- Official repository qtmleap/Interceptor-Plugins, branch main, feed https://qtmleap.github.io/Interceptor-Plugins/repository.json.
- Repository UUID 90A213C0-9D3C-47F5-ABB8-C15C7472E2AD; plugin UUIDs 76532D8C-608A-4EA3-AC16-755BABF2AB7E and 5B478646-4A70-4EF1-B04B-6CB63450E5A4.
- Metadata only, example.com, body:none, preview binding; synthetic dry run and display-only actions.
- Official feed must be signed; no key or expiring repository.json in Git; secret only in main-restricted environment.
- Codex owns integration, workflow, key and publishing. Claude edits only assigned files; no worker commits/pushes.

## Review Focus

- Incorrect event shape may return plausible undefined text: execute known app fixtures and compare literal expected JSON.
- A POST or status just outside 500...599 must produce no action: use explicit negative cases.
- Template users may retain official identity: reject official UUID/URL/fingerprint under another configured repository.
- A changed package or payload must fail integrity/authentication: test actual byte tampering through production validators.
- Expired metadata, stale main, redirects and uncertain deployment must not silently reset state or republish: fail closed and retry reads only.

### Task 1: Editable samples, deterministic generation and verification tools

**Owner:** Claude implementation worker; native Swift execution by Codex.
**Files:** scripts/*.js, manifests/*.json, fixtures/*.json, repository-config.json, tools/build.py, tools/configure.py, tools/guard.py, tools/repository_config.py, tools/reserved.json, tools/Verifier/**, tests/**.

**Interfaces:**
- Config fields: schemaVersion=1, id, name, githubRepository, repositoryURL, publicKeyFingerprint (null before key creation), upstreamRevision (fixed SHA).
- `python3 tools/build.py --root ROOT --output DIRECTORY`: create plugins/*.json and .nojekyll only; no publisher/keys/network. Reject missing pairs, symlinks, duplicate IDs and invalid names.
- `python3 tools/configure.py --root ROOT --repository OWNER/NAME --name NAME --url HTTPS_URL [--fingerprint HEX]`: allocate new repository/plugin UUIDs; clear official fingerprint; preserve source and upstream pin. Never modify official config accidentally; fail without changes for invalid input.
- `python3 tools/guard.py --root ROOT --repository OWNER/NAME --ref refs/heads/main`: signed deployment identity check; reserved official IDs/URL/fingerprint cannot be reused outside official owner/name, configured repository must match argument, fingerprint required.
- `tools/reserved.json`: schemaVersion=1, officialRepository=qtmleap/Interceptor-Plugins, ids (repository and plugin UUID strings), urls (official feed URLs), fingerprints (official current and retired fingerprints). configure.py and guard.py read the same file; retained entries survive migration.
- Swift package tools/Verifier depends via `../../.tools/interceptor/Packages/InterceptorAutomation`; executable `interceptor-samples-check`.
- `interceptor-samples-check samples ROOT DIRECTORY`: validate each package with PluginPackage, run fixtures/cases.json through production QuickJS and compare literal expected JSON/errors.
- `interceptor-samples-check verify-local ROOT DIRECTORY [--signed]`: verify envelope with configured URL/current time; expected repo UUID, every package hash/size/manifest; with --signed require configured fingerprint. Print JSON summary including sequence and fingerprint.
- `interceptor-samples-check verify-live ROOT SEQUENCE`: same identity/expiry rules (>=14 days) plus exact expected sequence; fetch all packages anonymously using production RepositoryClient (no redirects). No publishing/retry inside this command.
- `interceptor-samples-check previous ROOT FILE`: verify prior envelope's structure/signature/configured fingerprint/UUID even if expired, using its issuedAt as verification time; reject issuance >now+300s. Print sequence only. This is publication preflight, never app import or live success verification.
- previous parses only enough untrusted envelope/payload JSON to obtain issuedAt, then calls PUBLIC RepositoryEnvelope.verify(envelope:url:now:issuedAt); fingerprint/UUID/sequence come only from that verified snapshot. No internal APIs or @testable imports.
- fixtures/cases.json entries: name, plugin (basename), hook (request/response), event (object), expected (full result object) OR expectError=scriptError; shared fixtures/config.json matches app preview config.

- [ ] Write Python command tests first; record expected red run before implementing builder/configuration guards.
- [ ] Add request summary and response 5xx filter with app's nested request/response fields, manifests and independent literal expected cases (GET, POST, 503,500,599,200,499,600 and wrong hooks).
- [ ] Implement deterministic build, template configuration and signed identity guard; run Python suite green on worker host.
- [ ] Implement Swift driver using production validators/runtime/client; keep file and argument failures nonzero with concise diagnostics.
- [ ] Codex builds and executes native sample cases; run original broken sample as negative proof; verify deterministic builds.
- [ ] Freeze source fingerprints, review actual files independently and resolve material findings.

### Task 2: Reproducible checks, signing and Pages workflow

**Owner:** Codex.
**Files:** tools/bootstrap.sh, tools/check.sh, tools/publish.sh, tools/fetch_previous.py, .github/workflows/integration.yaml, .github/workflows/deployment.yaml, docs/maintaining.md.

**Consumes:** Task 1 CLIs and config exactly as above.
**Produces:** `tools/check.sh` local/full CI command; `tools/publish.sh` builds and signs build/site with sequence, writes build/sequence.txt; workflow deploys and then only re-reads.

- [ ] Bootstrap a sparse anonymous checkout at the exact pin; refuse pre-existing mismatched/dirty checkout. Record upstream SHA and toolchain under build/evidence.
- [ ] Check script runs Python suite, two deterministic generations, Swift build, sample cases, unsigned publisher and local verification, then signed temporary-key integration/tamper checks. Temp keys outside Git/public dirs, 0600, always removed. Never use official key for tests. Signed tests use a THROWAWAY ROOT/config copy containing the temporary fingerprint; never weaken the verifier or alter committed official config. Include wrong-fingerprint refusal.
- [ ] Previous-feed downloader uses bounded HTTPS GET, no redirects/cookies/auth; only HTTP404 permits first publish. Verify saved bytes with `previous` before choosing current Unix-ms sequence; require greater than prior value.
- [ ] Publish identity guard before key access, signed publisher with official key path outside checkout, source-main equality before deployment. Stop nonzero on stale source or invalid prior metadata.
- [ ] Pin action references to observed full SHAs. CI: PR/push on macos-15, contents:read, no signing environment. Publish: main push/manual/weekly, one concurrency group cancel-in-progress:false, main-restricted github-pages environment, contents:read/pages:write/id-token:write.
- [ ] After deploy, verify-live retries reads only for bounded CDN propagation; require exact sequence, fingerprint, >=14-day expiry and all hashes.
- [ ] Run shell syntax checks and workflow lint where available; inspect actual permissions and guards, no grepping-only security tests.

### Task 3: Documentation, independent review and official publication

**Owner:** Codex; independent Claude actual-files reviewer.
**Files:** README.md, README.ja.md, LICENSE, docs/maintaining.md, config fingerprint.

- [ ] Generate official Ed25519 key once with upstream publisher outside checkout; store securely, commit only public fingerprint. Document owner backup and loss/compromise recovery.
- [ ] Write English/Japanese registration, selected hook, expected outputs, template configuration, signed/unsigned trust and synthetic-only limits. State 30-day expiry and GitHub schedule inactivity limitation.
- [ ] Run full local checks on immutable source content; request fresh Claude actual-files review independent of implementer. Address concrete findings and recheck affected behavior.
- [ ] Use gh identity native checks, guarded Git and verified raw human authors for all commits/pushes. Preserve any AI attribution. Never push key/expiring metadata.
- [ ] Create public qtmleap/Interceptor-Plugins with template flag, main-restricted Pages environment, environment Secret; upload only completed reviewed source. Enable Pages Actions mode, inspect exact remote state after any uncertain write.
- [ ] Await actual CI, Pages deployment and anonymous verify-live completion. Confirm template, weekly workflow active and secret scoped to environment. Record evidence and report usable registration URL plus full public-key fingerprint.

## Execution

User authorized implementation/tests/publication without additional confirmation. Codex executes and integrates; Claude implements Task 1 after plan feasibility review. LocalGPT unavailable (browser disconnected); do not bypass it or claim a LocalGPT review. No simulator resources are needed for these logic/tooling tests.

Execution correction: the initial macos-15 runner selected Swift 6.1, which rejects the pinned library's actor-isolation code. CI now uses the official hosted xcode-27 image and explicitly selects Xcode 27.0.0 (Swift 6.4), matching the validated native toolchain. Bootstrap rejects older Swift before fetching. No upstream source or concurrency checking is changed; the package deployment target remains macOS 14.
