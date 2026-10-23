// SplatNet 3 Salmon Run acquisition. Requests are defined only in this file; results are stored with Interceptor.createFile.
// Pure SplatNet 3 Salmon Run result logic. No I/O, no host calls, no state.
type QueryPair = { history: string; detail: string }
type QueryCatalog = { versions: { [version: string]: QueryPair } }
type GraphQLRequest = {
  variables: { [name: string]: string }
  extensions: { persistedQuery: { version: 1; sha256Hash: string } }
}
type LogicCode =
  | 'missing-context' | 'unsupported-version' | 'invalid-catalog' | 'invalid-id'
  | 'invalid-response' | 'graphql' | 'limit'
type DetailCode =
  | 'recapture' | 'http' | 'query-rejected' | 'graphql' | 'invalid-response'
  | 'id-mismatch' | 'invalid-principal' | 'invalid-expected'
type DetailOutcome =
  | { kind: 'detail'; id: string }
  | { kind: 'unavailable' }
  | { kind: 'failure'; code: DetailCode }

const MAX_IDENTIFIER_BYTES = 512
const MAX_HISTORY_IDS = 256

const HASH = /^[0-9a-f]{64}$/
const has = (o: object, k: string): boolean => Object.prototype.hasOwnProperty.call(o, k)
const isObject = (v: unknown): v is { [k: string]: unknown } =>
  typeof v === 'object' && v !== null && !Array.isArray(v)

function fail(code: LogicCode): never {
  const e = new Error(code) as Error & { code: LogicCode }
  e.code = code
  throw e
}

function utf8Length(s: string): number {
  let n = 0
  for (const ch of s) {
    const c = ch.codePointAt(0) as number
    n += c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4
  }
  return n
}

function validIdentifier(v: unknown): v is string {
  return typeof v === 'string' && v.length > 0 && utf8Length(v) <= MAX_IDENTIFIER_BYTES
}

function checkPair(p: unknown): QueryPair {
  if (!isObject(p) || !has(p, 'history') || !has(p, 'detail')) return fail('invalid-catalog')
  const { history, detail } = p
  if (typeof history !== 'string' || typeof detail !== 'string' || !HASH.test(history) || !HASH.test(detail)) {
    return fail('invalid-catalog')
  }
  return { history, detail }
}

function versions(catalog: unknown): { [v: string]: unknown } {
  if (!isObject(catalog) || !has(catalog, 'versions') || !isObject(catalog.versions)) return fail('invalid-catalog')
  return catalog.versions
}

function resolveQueries(version: string, catalog: QueryCatalog): QueryPair {
  if (typeof version !== 'string' || version === '') return fail('missing-context')
  const map = versions(catalog)
  if (!has(map, version)) return fail('unsupported-version')
  return checkPair(map[version])
}

function makeHistoryQuery(pair: QueryPair): GraphQLRequest {
  const p = checkPair(pair)
  return { variables: {}, extensions: { persistedQuery: { version: 1, sha256Hash: p.history } } }
}

function makeDetailQuery(pair: QueryPair, id: string): GraphQLRequest {
  const p = checkPair(pair)
  if (!validIdentifier(id)) return fail('invalid-id')
  return { variables: { coopHistoryDetailId: id }, extensions: { persistedQuery: { version: 1, sha256Hash: p.detail } } }
}

function observationHashes(catalog: QueryCatalog): string[] {
  const map = versions(catalog)
  const out: string[] = []
  for (const key of Object.keys(map)) {
    const p = checkPair(map[key])
    for (const h of [p.history, p.detail]) if (out.indexOf(h) < 0) out.push(h)
  }
  return out
}

// errors: absent/null => none; non-empty array of objects => present; anything else malformed.
function hasGraphQLErrors(body: { [k: string]: unknown }): boolean | undefined {
  if (!has(body, 'errors') || body.errors === null) return false
  const e = body.errors
  if (!Array.isArray(e) || e.length === 0 || !e.every(isObject)) return undefined
  return true
}

function historyIDs(body: unknown): string[] {
  if (!isObject(body)) return fail('invalid-response')
  const errors = hasGraphQLErrors(body)
  if (errors === undefined) return fail('invalid-response')
  if (errors) return fail('graphql')
  if (!isObject(body.data) || !isObject(body.data.coopResult)) return fail('invalid-response')
  const result = body.data.coopResult
  const seen: string[] = []
  const lookup = new Set<string>()
  let present = 0
  for (const key of ['historyGroups', 'historyGroupsOnlyFirst']) {
    if (!has(result, key) || result[key] === undefined) continue
    present++
    const groups = result[key]
    if (!isObject(groups) || !Array.isArray(groups.nodes)) return fail('invalid-response')
    for (const group of groups.nodes) {
      if (!isObject(group) || !isObject(group.historyDetails) || !Array.isArray(group.historyDetails.nodes)) {
        return fail('invalid-response')
      }
      for (const item of group.historyDetails.nodes) {
        if (!isObject(item)) return fail('invalid-response')
        if (!validIdentifier(item.id)) return fail('invalid-id')
        if (lookup.has(item.id)) continue
        if (seen.length >= MAX_HISTORY_IDS) return fail('limit')
        lookup.add(item.id)
        seen.push(item.id)
      }
    }
  }
  if (present === 0) return fail('invalid-response')
  return seen
}

// Response text is parsed only to validate it; the original text is what gets saved.
function parseText(text: string): unknown {
  try { return JSON.parse(text) } catch (e) { return fail('invalid-response') }
}

const HISTORY_PATH = 'Salmon Run/history.json'
// Result IDs may be 512 characters with base64 slashes, so file names use a fixed-length ASCII digest of the UTF-8 ID.
const detailPath = (id: string): string => 'Salmon Run/details/' + sha256Hex(id) + '.json'

const SHA256_K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]

function utf8Bytes(s: string): number[] {
  const out: number[] = []
  for (const ch of s) {
    const c = ch.codePointAt(0) as number
    if (c < 0x80) out.push(c)
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63))
    else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
    else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
  }
  return out
}

// Pure SHA-256 of the UTF-8 bytes of `text`, as 64 lowercase hex digits.
function sha256Hex(text: string): string {
  const bytes = utf8Bytes(text)
  const bitLength = bytes.length * 8
  bytes.push(0x80)
  while (bytes.length % 64 !== 56) bytes.push(0)
  const high = Math.floor(bitLength / 0x100000000)
  for (const word of [high, bitLength >>> 0]) bytes.push((word >>> 24) & 255, (word >>> 16) & 255, (word >>> 8) & 255, word & 255)
  const h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
  const w: number[] = []
  for (let offset = 0; offset < bytes.length; offset += 64) {
    for (let i = 0; i < 16; i++) {
      const j = offset + i * 4
      w[i] = ((bytes[j] as number) << 24 | (bytes[j + 1] as number) << 16 | (bytes[j + 2] as number) << 8 | (bytes[j + 3] as number)) >>> 0
    }
    for (let i = 16; i < 64; i++) {
      const a = w[i - 15] as number, b = w[i - 2] as number
      const s0 = ((a >>> 7) | (a << 25)) ^ ((a >>> 18) | (a << 14)) ^ (a >>> 3)
      const s1 = ((b >>> 17) | (b << 15)) ^ ((b >>> 19) | (b << 13)) ^ (b >>> 10)
      w[i] = ((w[i - 16] as number) + s0 + (w[i - 7] as number) + s1) >>> 0
    }
    let [a, b, c, d, e, f, g, hh] = h as [number, number, number, number, number, number, number, number]
    for (let i = 0; i < 64; i++) {
      const t1 = (hh + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7)))
        + ((e & f) ^ (~e & g)) + (SHA256_K[i] as number) + (w[i] as number)) >>> 0
      const t2 = ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10)))
        + ((a & b) ^ (a & c) ^ (b & c))) >>> 0
      hh = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0
    }
    const next = [a, b, c, d, e, f, g, hh]
    for (let i = 0; i < 8; i++) h[i] = ((h[i] as number) + (next[i] as number)) >>> 0
  }
  return h.map(v => ('00000000' + v.toString(16)).slice(-8)).join('')
}

const failure = (code: DetailCode): DetailOutcome => ({ kind: 'failure', code })

function rejectedPersistedQuery(errors: unknown[]): boolean {
  return errors.some((e) => {
    if (!isObject(e)) return false
    const code = isObject(e.extensions) ? e.extensions.code : undefined
    return code === 'PERSISTED_QUERY_NOT_FOUND' || e.message === 'PersistedQueryNotFound'
  })
}

/** Player IDs are opaque and scoped to each result; validate their presence, not equality across results. */
function inspectDetail(
  status: number,
  body: unknown,
  expectedID: string,
): DetailOutcome {
  if (!validIdentifier(expectedID)) return failure('invalid-expected')
  if (status === 401 || status === 403) return failure('recapture')
  if (status === 404) return { kind: 'unavailable' }
  if (!Number.isInteger(status) || status < 200 || status > 299) return failure('http')
  if (!isObject(body)) return failure('invalid-response')
  const errors = hasGraphQLErrors(body)
  if (errors === undefined) return failure('invalid-response')
  if (errors) return failure(rejectedPersistedQuery(body.errors as unknown[]) ? 'query-rejected' : 'graphql')
  if (!isObject(body.data) || !has(body.data, 'coopHistoryDetail')) return failure('invalid-response')
  const detail = body.data.coopHistoryDetail
  if (detail === null) return { kind: 'unavailable' }
  if (!isObject(detail)) return failure('invalid-response')
  if (detail.id !== expectedID) return failure('id-mismatch')
  const player = isObject(detail.myResult) && isObject(detail.myResult.player) ? detail.myResult.player : undefined
  if (!player || !validIdentifier(player.id)) return failure('invalid-principal')
  return { kind: 'detail', id: detail.id }
}

// Query IDs are pinned to the captured web-view version; provenance: docs/development/splatnet3-queries.json.
const QUERY_CATALOG: QueryCatalog = {
  "versions": {
    "4.0.0-091d4283": {
      "history": "0f8c33970a425683bb1bdecca50a0ca4fb3c3641c0b2a1237aedfde9c0cb2b8f",
      "detail": "824a1e22c4ad4eece7ad94a9a0343ecd76784be4f77d8f6f563c165afc8cf602"
    },
    "10.0.0-d15503c4": {
      "history": "e11a8cf2c3de7348495dea5cdcaa25e0c153541c4ed63f044b6c174bc5b703df",
      "detail": "f2d55873a9281213ae27edc171e2b19131b3021a2ae263757543cdd3bf015cc8"
    }
  }
}

Interceptor.attach({
  response: {
    async onLeave(res, cfg) {
      if (res.status !== 201 || !isObject(res.body)) return
      const token = res.body.bulletToken
      if (typeof token !== 'string' || token.length === 0) return
      if (token.length > 4096 || !/^[\x21-\x7e]+$/.test(token)) throw new Error('invalid-token')
      const headers = res.request.headers || {}
      const version = headers['x-web-view-ver'] || ''
      const pair = resolveQueries(version, QUERY_CATALOG)
      const language = typeof res.body.lang === 'string' && res.body.lang
        ? res.body.lang : headers['accept-language']
      if (!language) throw new Error('missing-context')
      const limit = cfg.settings?.maxResults ?? 50
      if (typeof limit !== 'number' || !Number.isInteger(limit) || limit < 1 || limit > 50) {
        throw new Error('invalid-limit')
      }
      const requestHeaders: { [name: string]: string } = {
        authorization: 'Bearer ' + token,
        'content-type': 'application/json',
        'x-web-view-ver': version,
        'accept-language': language,
        'x-requested-with': 'XMLHttpRequest',
      }
      if (headers['user-agent']) requestHeaders['user-agent'] = headers['user-agent']
      // Do not forward Nintendo login cookies. A captured BulletToken authorizes GraphQL.
      const endpoint = 'https://api.lp1.av5ja.srv.nintendo.net/api/graphql'
      const history = await fetch(endpoint, {
        method: 'POST', headers: requestHeaders, body: JSON.stringify(makeHistoryQuery(pair)),
      })
      if (history.status === 401 || history.status === 403) throw new Error('recapture')
      if (!history.ok) throw new Error('http')
      const historyText = await history.text()
      const ids = historyIDs(parseText(historyText))
      await Interceptor.createFile({ storage: Interceptor.Storage.iCloudDrive, atPath: HISTORY_PATH, contents: historyText })
      const acquired: string[] = []
      const unavailable: string[] = []
      for (const id of ids.slice(0, limit)) {
        const reply = await fetch(endpoint, {
          method: 'POST', headers: requestHeaders, body: JSON.stringify(makeDetailQuery(pair, id)),
        })
        // Error responses need not contain JSON. Never retry an expired token.
        if (reply.status === 401 || reply.status === 403) throw new Error('recapture')
        if (reply.status === 404) { unavailable.push(id); continue }
        if (!reply.ok) throw new Error('http')
        const text = await reply.text()
        const data = parseText(text)
        const checked = inspectDetail(reply.status, data, id)
        if (checked.kind === 'failure') throw new Error(checked.code)
        if (checked.kind === 'unavailable') { unavailable.push(id); continue }
        // Save the validated response text as received; a failed save stops the chain.
        await Interceptor.createFile({ storage: Interceptor.Storage.iCloudDrive, atPath: detailPath(id), contents: text })
        acquired.push(id)
      }
      // Existing diagnostic action; not an HTTP send. Never include the token or result bodies.
      return { actions: [{
        type: 'webhook', endpointId: '8B71B789-357C-44D8-AF3A-1D8192234BB5',
        json: { version, acquired, unavailable, remaining: Math.max(0, ids.length - limit) },
      }] }
    },
  },
})
