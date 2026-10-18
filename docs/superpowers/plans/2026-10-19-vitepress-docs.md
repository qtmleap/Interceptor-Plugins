# Bilingual VitePress Documentation Implementation Plan

> **For agentic workers:** Use the recorded parallel implementation assignments and independent review chain. Codex owns integration, verification and publication; workers do not commit or deploy.

**Goal:** Publish a Japanese/English VitePress documentation site with Bun while preserving the signed plugin feed.

**Architecture:** Curated Markdown in `website/` uses the default theme. A read-only docs job builds a static artifact; the existing protected publisher combines it with its unchanged signed feed output and performs one Pages deployment.

**Tech Stack:** VitePress 1.6.4, Bun 1.3.6, existing Python 3 tooling, existing Swift/QuickJS publisher and verifier.

**Spec:** `docs/superpowers/specs/2026-10-19-vitepress-docs-design.md`.

## Global constraints

- Japanese root, English `en/`, seven matching page slugs and localized navigation/search.
- Only the shipped synchronous v1 synthetic preview; at most two returned actions and no webhook delivery/live/background execution.
- Keep official package bytes, upstream revision, signing identity, feed/package URLs and protected release gates intact.
- No npm, secondary Pages publisher, new credentials, analytics/CDN, or public internal planning documents.
- Public Markdown is product input and cannot receive the human-only documentation CI exemption.

## Review focus

- A cloned repository uses its own base, name, feed URL and fingerprint, including an unset fingerprint or a display name containing HTML/Vue delimiters. Pin this with context/render tests.
- Website content cannot collide with or modify a feed/package path. Pin exact copied bytes, reserved paths and no partial output with composition tests.
- Symlink/special/hidden artifacts cannot bring private/build inputs into Pages. Pin refusal cases in composition tests.
- Locale switching, search, anchors and subpath assets work on actual built pages. Check built links and browser interactions.
- Signing/upload success alone does not prove website or consumer availability. Read public pages and verify the exact deployed sequence/packages with the existing native client.

## Task 1: Public content

Owner: Claude content job `job_bfd5437d8f080e2fa407a45a7975b785`; subsequent small integration corrections by Codex.

Files: `website/*.md`, `website/en/*.md`, `README.md`, `README.ja.md`, `docs/maintaining.md`.

Interface: matching slugs `index`, `getting-started`, `authoring`, `api`, `examples`, `publishing`, `devcontainer`; explicit metadata tokens in the spec; relative canonical source includes.

- [x] Write both locales from actual TypeScript, manifest, fixture and setup contracts.
- [x] Independent actual-content review `job_b8a2770657f934eff2a182d824dd76c4` completed.
- [x] Correct concrete completeness issues: prerequisites, new plugin UUID/fixture format, auth-recovery lifecycle, path matching, setup recovery and trust explanations.
- [x] Verify updated content together with the rendered site and final source review.

## Task 2: Build and composition

Owner: Claude infrastructure job `job_b05636012e21aaf4999f81cb47ad744c`.

Files: `website/.vitepress/`, `package.json`, `bun.lock`, new `tools/*docs*` and `tools/compose_pages.py`, corresponding tests.

Interfaces: validated context from `repository-config.json`; `build/docs` static website; `compose_pages.py --feed build/site --docs build/docs --output build/pages`.

- [x] Add pinned dependency/scripts and safe metadata substitution.
- [x] Add focused context/composition tests; worker host has no Python/Bun, so it cannot claim execution. Codex runs native tests and records actual outcomes.
- [x] Build the default and customized site, checking local links/assets/anchors and locale parity.
- [ ] Preserve every signed feed/package byte through composition, then run the existing signed verifier on the combined output.

## Task 3: CI and publication integration

Owner: same infrastructure worker; Codex verifies actual workflow source and official action pins.

Files: `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, configured-template test input list.

- [x] Add an always-running read-only docs check to PR/master CI.
- [x] Build/upload docs without a signing environment or Pages/OIDC write permissions in the existing publishing workflow.
- [ ] Download the same-run docs artifact, compose once, verify signed combined output, upload/deploy `build/pages` through existing gates.
- [x] Keep all existing full checks, environment/branch/stale-ref checks, renewal and cleanup paths.

## Task 4: Integration, review and rollout

Owner: Codex; fresh read-only Claude infrastructure reviewer chain `job_60417debdb80f977eeaf2c063ec9d57a` for final actual-file delta. LocalGPT handles a separate UI-only review if its current capability permits the visible evidence.

- [x] Capture live baseline sequence `1792321080848`, both package hashes and native live signature verification.
- [x] Baseline portable checks: 69 main tests and 9 tool tests passed.
- [ ] Freeze source hashes; run appropriate native docs/full package checks and actionlint without concurrent edits.
- [ ] Check desktop/mobile Japanese/English, navigation, local search and highlighted code in a real browser.
- [ ] Resolve actual review findings and recheck affected behavior.
- [ ] Apply native Git identity/message/outgoing checks, create and attach a PR, and await all exact-head CI success.
- [ ] Merge normally at the verified head, track the resulting Pages workflow, verify public documentation and exact signed feed/package availability.
- [ ] Save evidence, stop owned preview processes, and archive completed managed review chats. Native chat archival currently has a recorded rate-limit backoff; do not discard its pending cleanup record.
