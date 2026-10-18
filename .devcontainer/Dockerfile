# Adapted from qtmleap/devcontainers examples/hono-node at 7d1931f8d33e49dee3775b1d893297ced0c639bf.
FROM oven/bun:1.3.6@sha256:f20d9cf365ab35529384f1717687c739c92e6f39157a35a95ef06f4049a10e4a AS bun
FROM mcr.microsoft.com/devcontainers/base:dev-ubuntu24.04@sha256:2304776586353b17596b4785fc0a4b30c024c9a9c74aa60d4e87253e7e141832

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
RUN test "$(bun --version)" = '1.3.6'
