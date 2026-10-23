// SplatNet 3 Salmon Run acquisition. Requests are defined only in this file.
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
  | 'id-mismatch' | 'invalid-principal' | 'principal-mismatch' | 'invalid-expected'
type DetailOutcome =
  | { kind: 'detail'; id: string; principal: string }
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

const failure = (code: DetailCode): DetailOutcome => ({ kind: 'failure', code })

function rejectedPersistedQuery(errors: unknown[]): boolean {
  return errors.some((e) => {
    if (!isObject(e)) return false
    const code = isObject(e.extensions) ? e.extensions.code : undefined
    return code === 'PERSISTED_QUERY_NOT_FOUND' || e.message === 'PersistedQueryNotFound'
  })
}

/** Pass null only while establishing principal from the first validated detail.
 * Once established, every subsequent detail must pass that known principal.
 * Omission is rejected at runtime as well as by the TypeScript signature.
 */
function inspectDetail(
  status: number,
  body: unknown,
  expectedID: string,
  expectedPrincipal: string | null,
): DetailOutcome {
  if (!validIdentifier(expectedID)) return failure('invalid-expected')
  if (expectedPrincipal !== null && !validIdentifier(expectedPrincipal)) return failure('invalid-expected')
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
  if (expectedPrincipal !== null && player.id !== expectedPrincipal) return failure('principal-mismatch')
  return { kind: 'detail', id: detail.id, principal: player.id }
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
      const ids = historyIDs(await history.json())
      const results: { id: string; result: unknown }[] = []
      const unavailable: string[] = []
      let principal: string | null = null
      for (const id of ids.slice(0, limit)) {
        const reply = await fetch(endpoint, {
          method: 'POST', headers: requestHeaders, body: JSON.stringify(makeDetailQuery(pair, id)),
        })
        // Error responses need not contain JSON. Never retry an expired token.
        if (reply.status === 401 || reply.status === 403) throw new Error('recapture')
        if (reply.status === 404) { unavailable.push(id); continue }
        if (!reply.ok) throw new Error('http')
        const data: unknown = await reply.json()
        const checked = inspectDetail(reply.status, data, id, principal)
        if (checked.kind === 'failure') throw new Error(checked.code)
        if (checked.kind === 'unavailable') { unavailable.push(id); continue }
        principal = checked.principal
        // Raw result JSON is available here for a later, ordinary fetch upload.
        // This acquisition-only Plugin does not upload or persist it.
        results.push({ id, result: (data as { data: { coopHistoryDetail: unknown } }).data.coopHistoryDetail })
      }
      // Existing diagnostic action; not an HTTP send. Never include the token or result bodies.
      return { actions: [{
        type: 'webhook', endpointId: '8B71B789-357C-44D8-AF3A-1D8192234BB5',
        json: { version, acquired: results.map(item => item.id), unavailable, remaining: Math.max(0, ids.length - limit) },
      }] }
    },
  },
})
