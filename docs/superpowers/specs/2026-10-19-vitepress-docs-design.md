# Bilingual plugin documentation

The user requested VitePress, Bun, Japanese and English, and publication to the existing GitHub Pages project. Use the framework's standard documentation theme and components, without a separate custom UI or a new hosting provider.

## Public content and navigation

Keep public Markdown in `website/`, separate from internal development plans. Japanese is the root locale and English uses `en/`. Both locales have the same seven pages: `index`, `getting-started`, `authoring`, `api`, `examples`, `publishing`, and `devcontainer`. Use matching slugs, localized navigation/sidebar/search, standard code highlighting, responsive navigation, and default light/dark themes. The homepage offers adding the repository and writing a plugin as its two primary actions.

Describe the actual published synchronous v1 synthetic-preview contract. It returns at most two webhook intents and does not send them, attach to captured traffic, or run in the background. Embed canonical TypeScript, manifest and type files in examples rather than maintaining copies. Keep the existing detailed maintenance/security documentation available through source links; update its publishing-output references to the new combined artifact.

Use explicit `%%REPOSITORY_NAME%%`, `%%REPOSITORY_URL%%`, `%%FINGERPRINT%%`, `%%GITHUB_REPOSITORY%%`, `%%BUN_VERSION%%` tokens where configuration is displayed. The build substitutes them safely in text, fenced code and links. Derive validated metadata and the Pages base from `repository-config.json`, using the existing Python config validator. A custom repository must not inherit the official feed identity, and an unset fingerprint is described as unconfigured. Escape display names as text, including HTML and Vue delimiters. Upstream product/devcontainer references remain explicit upstream links.

## Build and single publication owner

Pin stable VitePress 1.6.4 with Bun 1.3.6 and a frozen lockfile. Run the VitePress executable under Bun. All generated context/cache/site data stays in ignored `build/`. `build/site` remains the existing signed feed output with exactly the existing package bytes. Documentation builds separately to `build/docs`.

In the existing publish workflow, build/check docs in a separate read-only Linux job without an environment, secrets, Pages write or OIDC permissions. Upload a short-lived artifact pinned to that workflow run. The protected publishing job downloads it, runs existing package/QuickJS/integrity checks, restores the key through the existing path, and signs the feed. A standard-library Python composition tool then stages one `build/pages` artifact. Reject collisions with `repository.json`, `plugins`, or `.nojekyll`; reject unsafe links/file types, unexpected hidden entries and unreasonable artifact sizes. Preserve each feed/package byte and verify the resulting signed feed with the existing native verifier before uploading. Keep the existing master/environment/stale-ref/sequence/expiry/cleanup gates, schedule and single concurrency group. No second Pages publisher, signature-schema changes, new keys or credentials.

Documentation changes never use the human-only Markdown CI exemption. An always-running read-only docs CI job builds and checks locale parity, internal links/anchors, local assets/search, and source includes. Existing full CI remains intact. Update the configured-template test's copied inputs where needed. Avoid brittle prose keyword tests; correctness is checked against canonical source and independent review.

## Verification and rollout

Baseline portable authoring tests passed before changes. Save pre-release live feed/package hashes. Unit tests exercise actual composition preservation and refusal cases, plus metadata/base derivation. Build official and independently customized documentation to check template portability. Native Codex verifies the actual diff, desktop/mobile pages, search, language switching and source highlighting. Obtain an independent Claude review of the actual source. Publish through a reviewed PR after its actual CI succeeds, then verify Japanese/English public routes and the exact new signed-feed sequence/package hashes. Keep unpublished user changes untouched.

LocalGPT's conceptual plan review and Claude's actual-file feasibility review completed independently. Their artifact-integrity, isolated-build, template, and locale findings are incorporated here. LocalGPT actual-file access was previously blocked; do not represent its conceptual review as source inspection. User requested implementation and publication; no new hosting, branding or flow choice is being introduced beyond the selected VitePress theme.
