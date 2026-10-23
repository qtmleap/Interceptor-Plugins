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
grant and trusted save callback (host wait excluded),120sec wall,
64requests,1MiB per response and16MiB aggregate; two concurrent fetch VMs.

repository-config.json pins the shared native source used by the simulator.
`run-package-fetch` uses that exact C bridge and an offline request/response
fixture protocol. Generated-Salmon-Plugin fixtures establish request order,
JSON bodies, filtering and errors; native transport tests use an owned TLS
origin. Those checks alone do not establish Nintendo acceptance; that needs real
captured-token and device/service verification. M3 verification confirmed actual
history and detail response JSON saving. Interceptor.saveJSON stores the original
JSON text with the write.files grant; external upload remains deferred.
