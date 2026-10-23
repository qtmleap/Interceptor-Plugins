# SplatNet 3 fetch integration

The Plugin reads `res.body.bulletToken` in the existing response.onLeave hook;
that captured response body never needed a new API. GraphQL calls use global
fetch with URL/method/headers/body in JS, without an outbound manifest section.

The paired Interceptor change implements standard fetch in QuickJS for this
hook. The read-only scheduling probe preserves synchronous hooks and defers
only fetch/Promise hooks until after phase admission is released. The dedicated
VM thread bridges to bounded async NIO transport. Revocation/shutdown cancels
and drains the VM and transport. No UI, credential pool or proprietary JS
sending API is added.

Supported subset: public HTTPS443 GET/POST/PUT with strict JSON request bodies
(up to8KiB), no URL query/redirect/stream/compressed response or automatic cookie.
Response.status/ok/bodyUsed/text()/json() are available; read the body once.
Limits:8MiB JS heap,250ms cumulative CPU for fetch-only or1000ms with a files
grant and trusted file callback (host wait excluded),120sec wall,
64requests,1MiB per response and16MiB aggregate; two concurrent fetch VMs.

repository-config.json pins the shared native source used by the simulator.
`run-package-fetch` uses that exact C bridge and an offline request/response
fixture protocol. Generated-Salmon-Plugin fixtures establish request order,
JSON bodies, filtering and errors; native transport tests use an owned TLS
origin. Those checks alone do not establish Nintendo acceptance; that needs real
captured-token and device/service verification. Previous M3 verification confirmed
history and 50 detail response JSON files with the earlier local-save API.

`Interceptor.createFile({storage, atPath, contents})` durably stages original bytes
with the `write.files` grant. `Interceptor.Storage` supplies `local` and
`iCloudDrive`; the latter uses a user-authorized folder mapped to a prefix of the
virtual storage root. For `atPath: 'Salmon Run/history.json'`, selecting the actual
`iCloud Drive/Salmon Run` folder grants prefix `Salmon Run`. The publisher strips
that exact component prefix once and writes `history.json` directly there; it does
not create a second Salmon Run folder. The main application exports
while foreground, retaining private records for retry on folder/provider failure.
Promise success means the private commit, not iCloud server upload. The simulator
observes requests through its offline CREATEFILE/CREATED protocol and never writes
files. Actual createFile/iCloud M3 acceptance is a separate device check.

The acquisition Plugin checks only the fields needed to follow result IDs and
associate a response with its requested file, plus HTTP/GraphQL errors and the
configured request limit. Gameplay/player fields are stored without schema
validation. IDs are opaque nonempty strings; filenames remain fixed SHA-256
hex digests, and native request/body limits still apply. Detailed validation
belongs downstream. Response text is saved as received, including unknown fields.
