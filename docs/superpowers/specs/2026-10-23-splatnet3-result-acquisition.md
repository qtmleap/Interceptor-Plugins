# SplatNet 3 Salmon Run acquisition Plugin

Updated 2026-10-23 to match the user's corrections. This replaces the earlier
workflow/native-credential/approval-UI proposal, which was outside the request.

## Requested behavior

- Implement in Interceptor-Plugins, without overlapping ongoing Interceptor work.
- Hook the successful POST `/api/bullet_tokens` response using `response.onLeave`.
- Read `res.body.bulletToken` and the granted request version/language headers.
- Use ordinary JavaScript `fetch` POSTs to `/api/graphql`: CoopHistoryQuery,
  then CoopHistoryDetailQuery for each distinct history ID, in history order.
- Keep outgoing URL, method, headers and body solely in the JavaScript. There is
  no `outbound` manifest section and no use of `Interceptor.send`.
- Retrieve and validate raw result objects inside the JS invocation. External
  uploads and persistent storage are deferred. No new UI or proprietary API.

## Behavior and limits

Only HTTP201 with a nonempty printable token starts a run. Query hashes must
match the captured `x-web-view-ver`; unknown versions fail rather than guess.
The bundled, source-pinned mapping is `4.0.0-091d4283`. Its presence in public
sources does not prove current Nintendo acceptance.

History IDs are deduplicated. More than256 distinct IDs fail explicitly rather
than silently claiming a partial history. Language comes from the token response
`lang` or captured Accept-Language, with no guessed fallback. At most `settings.maxResults` details are fetched
(default50, range1–50). The existing diagnostic result records acquired and
unavailable IDs, version and remaining count; it contains no token or raw body.
The live host currently discards diagnostic webhook actions, so this is fixture
output, not a new notification, saved result, or external HTTP request.

401/403 stops immediately and requires a fresh token capture. No token refresh,
login or retry is implemented. Missing details (404/null) are skipped; other HTTP
errors, GraphQL errors, wrong IDs or a changed player stop the run. A failed run
must not claim complete acquisition. Raw detail JSON exists only during JS
execution and is available at the validated `results.push` call for future
upload work. It is not persisted after the invocation.

## Compatibility and evidence

The SDK declares standard `fetch` authoring and allows awaited response.onLeave.
The paired native change supplies standard global fetch in QuickJS and awaits
the hook without adding a proprietary JS API. repository-config.json pins that
shared bridge for Rust simulator verification. Native transport and iOS tests
are separate from the offline Plugin fixtures; real Nintendo acceptance remains
unverified.

Acceptance for this Plugin change: actual Bun build emits the new JS, generated
manifest and package; fixtures run both authored and generated code and inspect
the real request bodies, sequence and errors; compiler regressions stay green.
Fixture fetch is offline and is not native-host or real Nintendo verification.
If UI comparison later becomes necessary, use the existing Mock Diff workflow.
