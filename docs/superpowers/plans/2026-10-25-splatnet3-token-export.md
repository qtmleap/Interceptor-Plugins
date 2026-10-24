# SplatNet 3 Token Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export a newly issued Bullet Token and context to iCloud `SplatNet3/auth.json` for Mac-side JSON acquisition.
**Architecture:** A separately enabled schema-2 Plugin hooks the existing token response and awaits the existing file API. Keep all networking and native host behavior unchanged.
**Tech Stack:** TypeScript, Bun, existing QuickJS simulator and Python unittest.
**Spec:** `docs/superpowers/specs/2026-10-25-splatnet3-token-export-design.md` (user-approved).

## Global Constraints

- Use const bindings and existing `Interceptor.createFile` / `Interceptor.Storage.iCloudDrive`; no dependencies, UI, host API, fetch or Game Web Token export.
- Export exactly `bulletToken`, `webViewVersion`, `language`, optional `userAgent`, at `SplatNet3/auth.json`; two-space JSON plus final newline. No real credentials in tests/logs/source.
- Follow the spec's header-safe text predicate, fallback rules, minimal validation and file-publication contract. Unknown web versions are accepted.
- Reuse the existing Plugins worktree, branch `codex/splatnet3-token-export` from reviewed base `6ebcc74`. Native Interceptor source is read-only.

## Review Focus

- Malformed/empty/control-character credentials: no saved unusable record and no token in failures.
- Missing/invalid response language: use a valid captured request language, otherwise generic error.
- New/unknown web version: export without a query-version allowlist.
- Repeat issuance and publication failure: same destination with newest staged content; external ownership checks remain intact.
- Build permissions/routing: generated script and manifest match the package; no FETCH instruction or body mutation.

### Task 1: Packaged Token Export Plugin

**Files:** Create `plugins/splatnet3-token-export/plugin.json`, `README.md`, `hooks/api.lp1.av5ja.srv.nintendo.net/api/bullet_tokens/POST.ts`, and `tests/test_splatnet3_token_export.py`. Integrator owns this spec/plan and any root fixture inventory adjustment.
**Interfaces:** Consume a granted `Interceptor.ReadOnlyResponseLeg` with status/body/request headers. Produce one awaited createFile with `icloud`, `SplatNet3/auth.json`, the specified bytes, and no diagnostic actions.

- [ ] Write simulator tests using the actual built package and synthetic credentials. Cover each Review Focus case, body.lang type variants, optional UA, non-201, missing token/version/language, repeat issuance, write rejection, no FETCH/results secret leakage, exact grant/routing and embedded artifact equality.
- [ ] Run those tests before adding the Plugin; confirm failure is the missing package.
- [ ] Implement the small TS hook and manifest with a fresh UUID and UTC publishedAt. Return for non-201/invalid token, throw generic `missing-context` for unavailable version/language, await the file write, and return no actions.
- [ ] Add Japanese usage documentation including folder authorization, foreground sync, read-only Mac consumption, field/header mapping, query-hash/variables requirement, and expiry/credential-file handling.
- [ ] Run targeted tests, lint, and normal `bun run build`. Verify one new script/manifest/package and compare unchanged existing outputs. Inspect relevant inventory tests; adjust only proven assumptions.
- [ ] Freeze changed-file hashes; request a fresh, separate read-only Claude actual-diff review. Integrator verifies findings and affected reruns.
- [ ] Commit and push through the native identity guard, open a draft PR against `codex/plugin-icons`, attach it, and inspect exact-head required CI. Keep fixture versus device/iCloud evidence separate; retain unknown/ongoing LocalGPT jobs and archive completed managed chats once no continuation remains.
