# Bun package bundling implementation plan

**Goal:** Let routed TypeScript plugins import QuickJS-compatible packages installed with Bun and bundle their dependency graph into one JavaScript file at build time.

**Architecture:** Keep TypeScript authored-hook validation and existing no-import output. Use normal Bun browser-target IIFE resolution against installed node_modules with no package-specific allowlist, export restriction or copied implementation. Dependencies remain managed through package.json and bun.lock. Do not add a runtime module loader, Node polyfills, native API or UI.

**Scope:** Static named/default/namespace/side-effect/type imports from installed package roots, scopes and exported subpaths; ESM, CJS, transitive package/internal relative dependencies; declaration typechecking. Authored relative-file imports and legacy schema1 behavior remain unchanged. Existing 128KiB output and client execution budgets remain. Unsupported Node builtins, dynamic imports, runtime require, native addons and unsupported assets must fail with an actionable build error. Browser targeting alone does not prove QuickJS compatibility; actual-runtime tests and docs describe that limit.

**Decisions:** Prefer Bun package resolution over a custom dependency resolver; dependencies/lockfile replace hardcoded per-package hashes. Generate stable code without checkout paths. Preserve dependency license comments/notices. Final guard must distinguish real unresolved host APIs from library-local names and safe feature detection. Host/phase restrictions continue on authored source; imported code remains subject to actual runtime grants and limits, and compilation is not a security boundary.

## Review focus
- Export conditions and scoped/subpath/transitive resolution, including browser vs Node entry.
- CJS bundler helpers and library-local identifiers must not be rejected as unresolved runtime APIs.
- Packages with declaration graphs/@types or without declarations must have understandable typechecking behavior.
- Unsupported builtins/assets/dynamic loading and missing package errors must identify cause without partial publication.
- Deterministic bundles, preserved licenses, unchanged no-import scripts, Salmon raw-save/hash behavior and full CI/template gates.

## Work
- [ ] Add generic fixture-package tests; observe failure on current js-sha256-only compiler.
- [ ] Replace dependency-specific import/hash bundling and typechecking with normal local Bun package bundling; preserve authored guards and no-import emission.
- [ ] Update hash tests to generic semantics and add shared C QuickJS runtime cases for multiple real dependency shapes. Remove obsolete pinned-hash mutation expectations; lockfile installation manages integrity.
- [ ] Document installation/import examples, actual supported runtime surface, failures and generated output. Run focused lint/compiler/Salmon tests then default build and required full checks on frozen content.
- [ ] Independent actual-file review, resolve material findings, native commit guard, update PR13 with final diff/scope and inspect CI on exact commit.

Codex coordinates and verifies native Mac evidence; Claude Code owns substantive implementation after independent LocalGPT and Claude feasibility review. No screenshots or device runs are required because runtime behavior and UI APIs are unchanged.

## Independent review decisions
Both LocalGPT (Thinking Standard, actual files through studio) and Claude Sonnet inspected the plan before implementation. Resolve type/runtime export conditions consistently (browser/import/default + types), CJS interop, type-only imports and declaration-graph diagnostics. Reject authored use of absent host APIs even if dependency typings add Node/DOM globals. Avoid requiring every type-only declaration to be runtime-compatible; imported declarations are not evaluated.

Keep compiler policy proportionate: Function/eval are standard QuickJS features and remain allowed in compatible dependencies; no new blanket dependency host-call ban or whole-JS compatibility validator. Diagnose unresolved runtime modules and known absent free host API uses, while permitting local names and safe typeof detection. Tests run the actual runtime, which remains authoritative. Static detection does not prove all branches compatible. Allow statically bundled dependency import() if it leaves no runtime import; authored dynamic loading stays unchanged.

Collect available package license/copying text and notices deterministically and include package name/version; do not invent license text or block private packages just for missing SPDX metadata. Preserve current no-import golden bytes and limits; no host path/banner leakage. Test two roots and NODE_ENV variants.

Use exact escape-string-regexp@5.0.0 (ESM) and fast-json-stable-stringify@2.1.0 (CJS) as small real integration fixtures, plus synthetic scoped/exported-subpath/transitive/type graph/feature-detection/unsupported API cases. `js-sha256` remains an ordinary dependency, with string hashing checked against hashlib. No dependency-specific hashes, resolver branches or argument/method restrictions remain.

Coordinator routing change: the Linux implementation worker was cancelled after environment/probe preparation and before product edits. Codex implements on the existing Mac toolchain; independent review remains separate. Extra owned Linux toolchains (243 MiB) were removed and verified after cancellation.

Actual-file reviews identified false rejections for UMD, namespace types and new.target, reversed feature conditions, builtin-name package collisions, and locale-dependent notice sorting. Regression tests reproduce these cases. Bun 1.3.6 prioritizes implicit builtin polyfills even over installed packages; only those collisions use pinned enhanced-resolve with browser/import/require conditions. Other package resolution stays with Bun. Package notices also retain root licenses when dist metadata repeats the package identity.
