# SplatNet 3 Token Export

## Intent

Export the user's own Bullet Token and required request context from Nintendo Switch App so a Mac-side collector can request SplatNet 3 JSON. The user approved this standalone Plugin, file contract and path on 2026-10-25.

## Approach

Add a separately enabled `splatnet3-token-export` Plugin. A dedicated Plugin makes credential-file creation explicit and independent of Salmon Run acquisition. Adding export to Salmon Run was considered, but would couple credential export to result acquisition and its version-specific queries. Passive page-response recording is a different workflow; the user selected token extraction for Mac-side collection.

## Behavior and file contract

- Hook the existing `POST /api/bullet_tokens` response with `response.onLeave` on `api.lp1.av5ja.srv.nintendo.net`.
- On HTTP 201, use the issued `bulletToken`, captured `x-web-view-ver`, and response `lang` (fall back to captured `accept-language`). Include captured `user-agent` only when nonempty.
- Save one JSON object with `bulletToken`, `webViewVersion`, `language`, and optional `userAgent` using `Interceptor.createFile` with `Interceptor.Storage.iCloudDrive` at `SplatNet3/auth.json`. A newly issued valid context replaces the same path; there is no credential history.
- The private record is replaced atomically. External publication updates only a file owned by this Plugin and unchanged since publication. A manually created/edited `auth.json` conflicts; the Mac collector treats the original as read-only. Do not weaken the publisher's ownership checks.
- Required values are strings with non-whitespace content and no ASCII control characters (U+0000 through U+001F or U+007F). Preserve valid values rather than normalize credentials. Use a valid response `lang`, otherwise a valid captured `accept-language`; omit invalid optional UA. Native event/file bounds remain authoritative; no arbitrary token-length cap or JWT schema is added. JSON uses the listed key order, two-space indentation and one final newline.
- Missing/invalid token or non-201 responses do not write. Missing version/language and write failures stop with generic errors; never expose credential contents in diagnostics or errors. Do not constrain the web version to the Salmon query table.
- Manifest: fresh stable UUID, schema 2, version 1.0.0 and explicit publication timestamp; read metadata `status`, headers `x-web-view-ver`, `accept-language`, `user-agent`, no query keys, JSON body. Enable only `write.files`, keep body edits false, and use empty endpoint bindings and settings.
- The user selects the iCloud Drive `SplatNet3` folder through the existing folder-grant flow. The Promise confirms private durable staging; foreground export and iCloud synchronization remain the host's responsibility.
- Authored source is TypeScript with const bindings. Use existing SDK APIs and minimum operational checks; no new dependencies, host API, UI, outgoing request, automatic renewal, or Game Web Token export.
- Document constructing GraphQL headers from this file on the Mac, including the fact that a valid token alone does not supply a query hash or variables. Use synthetic examples only. A bulk-query collector is a subsequent deliverable.
- README explains that the file contains plaintext authentication data, must not be shared/committed, and is not removed automatically on expiry. After authentication failure, reopen SplatNet3 to obtain a newly issued token and wait for foreground export/iCloud sync. Grant this Plugin its own `SplatNet3` folder. Token export can be enabled alone; simultaneous live scheduling with Salmon is not claimed by isolated fixtures.

## Verification

Exercise the built Plugin in shared QuickJS: valid export with optional UA and language fallback; malformed/missing context and non-201 no-write behavior; unknown web version accepted; write rejection; no fetch and no credentials in results/errors. Verify default `bun run build` generates its script, manifest and package, with exact embedded-script/manifest matches. Run lint and affected checks, then independent actual-diff review. Real Nintendo/M3 or iCloud export must be reported separately from fixture execution.
