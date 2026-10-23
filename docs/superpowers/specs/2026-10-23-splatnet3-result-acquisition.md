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
- Retrieve and validate result responses, then save their original JSON text with
  `Interceptor.createFile`. The user subsequently authorized native file saving.
  External uploads remain deferred; no new screens or custom HTTP API are added.

## Behavior and limits

Only HTTP201 with a nonempty printable token starts a run. Query hashes must
match the captured `x-web-view-ver`; unknown versions fail rather than guess.
The source-pinned query mappings cover `4.0.0-091d4283` and `10.0.0-d15503c4`.
The current 10.0.0 mapping has been exercised against Nintendo on M3; the older
4.0.0 mapping has offline fixture coverage.

History IDs are deduplicated. More than256 distinct IDs fail explicitly rather
than silently claiming a partial history. Language comes from the token response
`lang` or captured Accept-Language, with no guessed fallback. At most `settings.maxResults` details are fetched
(default50, range1–50). The existing diagnostic result records acquired and
unavailable IDs, version and remaining count; it contains no token or raw body.
The live host currently discards diagnostic webhook actions, so this is fixture
output, not a new notification, saved result, or external HTTP request.

401/403 stops immediately and requires a fresh token capture. No token refresh,
login or retry is implemented. Missing details (404/null) are skipped; other HTTP
errors, GraphQL errors, wrong result IDs or missing player IDs stop the run.
Player IDs are opaque and scoped to each result; all requests use the same
captured Bearer token. A failed run must not claim complete acquisition.

The validated history response and each validated detail response are saved
verbatim through `Interceptor.createFile` into `Interceptor.Storage.iCloudDrive`:
`Salmon Run/history.json` and `Salmon Run/details/<sha256 hex of the result ID>.json`.
The `write.files` grant is required. A failed save stops the chain. Saved JSON contains the original API response,
without a wrapper, authentication headers or a diagnostic summary. The native
host persists private files and exports their original bytes while the app is in
the foreground. The Plugin selects a path relative to the virtual storage root.
A native folder grant maps a matching component prefix to the actual selected
folder. Selecting iCloud Drive/Salmon Run therefore maps prefix Salmon Run and
publishes history.json directly there, without duplicating the folder component.
The Promise resolves on private publication;
iCloud provider delivery and Apple's server upload happen afterward.

## Compatibility and evidence

The SDK declares standard `fetch` authoring and allows awaited response.onLeave.
The paired native change supplies standard global fetch in QuickJS and awaits
the hook. The authorized JSON-saving API is declared by the SDK, compiler and
manifest validator. repository-config.json pins that shared bridge for Rust
simulator verification. Native transport and iOS tests
are separate from offline Plugin fixtures. Actual M3 verification confirms
nonempty history and detail response JSON saving; private verification evidence
contains file hashes and counts, never published credentials or result bodies.

Acceptance for this Plugin change: actual Bun build emits the new JS, generated
manifest and package; fixtures run both authored and generated code and inspect
the real request bodies, sequence and errors; compiler regressions stay green.
Fixture fetch is offline and is not native-host or real Nintendo verification.
If UI comparison later becomes necessary, use the existing Mock Diff workflow.
