---
title: Examples
lang: en-US
---

# Examples

"Request summary" and "Server error filter" are existing, real samples from the repository.

Long code blocks scroll horizontally. Use the code block’s copy control to copy the entire source.

## Request summary

On a completed `GET example.com` request, returns a `GET example.com/path` summary.

<<< ../../src/request-summary.ts{ts}

<<< ../../manifests/request-summary.json{json}

## Server error filter

Only for 5xx responses from `example.com`, returns the host and status.

<<< ../../src/server-error-filter.ts{ts}

<<< ../../manifests/server-error-filter.json{json}

Neither reads a body, headers or query values (`body.mode` is `none`), and both use only the `preview` binding. The synthetic test does not apply manifest filters, so the sources also check method, host and status.
