# SplatNet 3 Salmon Run Plugin implementation plan

Spec: ../specs/2026-10-23-splatnet3-result-acquisition.md

1. Promote the tested pure query/result logic into one canonical route source.
   Retain pinned query provenance in docs/development/splatnet3-queries.json.
2. Implement response.onLeave: read BulletToken, fetch history, deduplicate IDs,
   fetch bounded details, validate expected ID/player and stop on errors.
3. Enable standard fetch/async authoring in the existing SDK/compiler. Preserve
   synchronous restrictions elsewhere. No Interceptor.send, outbound declaration,
   UI, credential pool or native workflow framework.
4. Run failing-then-passing acquisition fixtures; run the generated JavaScript as
   well as TypeScript. Check request payloads, token/version propagation, errors,
   missing details, limits and absence of credential leakage.
5. Run actual bun run build. Inspect generated script, manifest, sourceFiles
   references and package. Record hashes and deterministic rebuild evidence.
6. Run repository authoring checks and a fresh independent Claude actual-file
   review. Resolve substantive findings. LocalGPT review was attempted but failed
   before dispatch due rate limiting; do not claim it completed.
7. Report native-fetch compatibility and real Nintendo verification separately
   from successful Plugin generation and offline fixture checks.

## Decisions

- User's corrected scope supersedes the previous native UI/workflow proposal.
- Reuse the existing isolated codex/splatnet3-plugin worktree.
- Later explicit user authorization adds QuickJS fetch in the paired Interceptor
  PR. Coordinate the shared C ABI and pin its verified commit, without duplicating
  other ongoing work. Verify the generated Plugin through that real C bridge.
- The previous draft's native credential storage, callback projection, schema3,
  approvals and local result UI are removed from this implementation plan.
