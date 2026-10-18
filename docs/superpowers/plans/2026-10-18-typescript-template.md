# TypeScript template implementation plan

**Goal:** Author plugins in TypeScript and initialize an independently signed GitHub Pages feed with one local command.

**Architecture:** Compile individual global scripts into ignored output, preserving the existing package/signature contract. Separate manifest identity validation from compilation. Add an idempotent local setup orchestrator around existing configuration and native key tooling.

**Spec:** ../specs/2026-10-18-typescript-template-design.md

## Constraints

- Preserve official UUIDs, signing key/fingerprint, master and v1 manifest schema.
- TypeScript 5.8.3, locked npm installation, synchronous hooks and JSON results.
- No keys in Git, artifacts, arguments or logs; PRs have no signing environment.
- No automatic commits, pushes, dispatches, secret replacement or key rotation.
- Root Interceptor checkout's README/docs and Git state are unrelated and preserved.

## Review focus

- Retry after partial API writes must keep IDs/key stable.
- Unknown existing secrets/protection policies must fail closed.
- Packaging cannot reuse stale generated JavaScript after a type failure.
- Equal helper/hook names in separate plugins must not collide.
- Compiled output must run in the actual bounded QuickJS host.

## Tasks

- [x] Add failing tests for TS compilation/packaging and host limitations; run red.
- [x] Implement SDK types, independent compiler, manifest-only loader and generated-source integration. Migrate samples and patch versions; run focused tests.
- [x] Add setup fake-API/interruption tests first, then implement local initialization with safe state reconciliation. No remote setup during development.
- [x] Integrate locked Node install into CI/check/publish and template smoke tests. Document TypeScript authoring and one-command setup in English/Japanese.
- [ ] Run complete Python, compiler, native QuickJS/integrity/template checks and workflow lint. Obtain fresh independent diff review; resolve material findings and verify actual changes.
- [ ] Preserve exact evidence and use mandatory guarded Git policy for any commit/push. Publication remains blocked if required online authentication/checks cannot execute; never bypass through an API or worker.

## Progress

Baseline: 33 Python tool tests passed in the isolated clone. Independent native reviewer completed the plan review; manifest/source separation, stable retry identity and synchronous host limits incorporated. Preferred LocalGPT/Claude MCP requests were rejected before execution by current approval policy, including after the user's permission; no such review is claimed. Native alternate review is used. GitHub's primary runner documentation confirms xcode-27 is a hosted image.

Final local evidence: 58 Python tests pass, bootstrap version-floor test passes, actionlint and diff whitespace checks pass, and a configured template passes the same 58 tests plus 14 real QuickJS cases. The changed native verifier was compiled directly with Swift 6.4 against existing release objects from the pinned upstream revision; emitted samples and temporary-key signature/package/payload/fingerprint checks pass. SwiftPM itself remains blocked by nested sandbox execution, and the 5 HTTPS fetch tests cannot bind their local server in this sandbox. These full gates are not reported as passing. No official key or remote setup was used. Independent native actual-diff reviews found and closed uncertain-secret overwrite, pre-setup environment creation and unemitted reference dependencies. Preferred MCP reviewers remain unavailable due host approval policy. Native GitHub network access is restricted; publication and CI remain pending.
