// SplatNet 3 Salmon Run acquisition. Requests are defined only in this file; results are stored with Interceptor.createFile.
import { sha256 } from 'js-sha256'

type QueryPair = { history: string; detail: string }
type GraphQLRequest = {
  variables: { [name: string]: string }
  extensions: { persistedQuery: { version: 1; sha256Hash: string } }
}
type Fields = { [key: string]: unknown }

const ENDPOINT = 'https://api.lp1.av5ja.srv.nintendo.net/api/graphql'
const HISTORY_PATH = 'Salmon Run/history.json'
const MAX_IDENTIFIER_BYTES = 512
const MAX_HISTORY_IDS = 256
const MAX_RESULTS = 50

// Query IDs are pinned to the captured web-view version; provenance: docs/development/splatnet3-queries.json.
const QUERIES: { [version: string]: QueryPair } = {
  '4.0.0-091d4283': {
    history: '0f8c33970a425683bb1bdecca50a0ca4fb3c3641c0b2a1237aedfde9c0cb2b8f',
    detail: '824a1e22c4ad4eece7ad94a9a0343ecd76784be4f77d8f6f563c165afc8cf602',
  },
  '10.0.0-d15503c4': {
    history: 'e11a8cf2c3de7348495dea5cdcaa25e0c153541c4ed63f044b6c174bc5b703df',
    detail: 'f2d55873a9281213ae27edc171e2b19131b3021a2ae263757543cdd3bf015cc8',
  },
}

const has = (o: object, k: string): boolean => Object.prototype.hasOwnProperty.call(o, k)
const isObject = (v: unknown): v is Fields => typeof v === 'object' && v !== null && !Array.isArray(v)

function fail(code: string): never {
  throw new Error(code)
}

function utf8Length(text: string): number {
  return [...text].reduce((bytes, ch) => {
    const code = ch.codePointAt(0) as number
    return bytes + (code < 0x80 ? 1 : code < 0x800 ? 2 : code < 0x10000 ? 3 : 4)
  }, 0)
}

// Result IDs are opaque; accept non-empty strings of at most 512 UTF-8 bytes.
function validIdentifier(v: unknown): v is string {
  return typeof v === 'string' && v.length > 0 && utf8Length(v) <= MAX_IDENTIFIER_BYTES
}

function queriesFor(version: string): QueryPair {
  if (version === '') return fail('missing-context')
  if (!has(QUERIES, version)) return fail('unsupported-version')
  return QUERIES[version] as QueryPair
}

function graphqlRequest(hash: string, variables: { [name: string]: string }): GraphQLRequest {
  return { variables, extensions: { persistedQuery: { version: 1, sha256Hash: hash } } }
}

function detailRequest(pair: QueryPair, id: string): GraphQLRequest {
  return validIdentifier(id) ? graphqlRequest(pair.detail, { coopHistoryDetailId: id }) : fail('invalid-id')
}

function requestHeaders(token: string, version: string, language: string, userAgent: string | undefined) {
  // Nintendo login cookies are never forwarded; the BulletToken authorizes GraphQL.
  return {
    authorization: 'Bearer ' + token,
    'content-type': 'application/json',
    'x-web-view-ver': version,
    'accept-language': language,
    'x-requested-with': 'XMLHttpRequest',
    ...(userAgent ? { 'user-agent': userAgent } : {}),
  }
}

// Result IDs may be 512 characters with base64 slashes, so file names use a fixed-length digest of the UTF-8 ID.
const detailPath = (id: string): string => 'Salmon Run/details/' + sha256(id) + '.json'

// Response text is parsed only to validate it; the original text is what gets saved.
function parseJSON(text: string): unknown {
  try { return JSON.parse(text) } catch (e) { return fail('invalid-response') }
}

// 401/403 mean the token expired; it is never retried.
function checkStatus(status: number): void {
  if (status === 401 || status === 403) fail('recapture')
  if (status < 200 || status > 299) fail('http')
}

// A GraphQL `errors` member is absent/null, or a non-empty array of objects; anything else is malformed.
function checkGraphQLErrors(body: Fields, context: 'history' | 'detail'): void {
  if (!has(body, 'errors') || body.errors === null) return
  const errors = body.errors
  if (!Array.isArray(errors) || errors.length === 0 || !errors.every(isObject)) fail('invalid-response')
  const queryRejected = context === 'detail' && errors.some(error =>
    error.message === 'PersistedQueryNotFound' ||
    (isObject(error.extensions) && error.extensions.code === 'PERSISTED_QUERY_NOT_FOUND'))
  fail(queryRejected ? 'query-rejected' : 'graphql')
}

function historyIDs(body: unknown): string[] {
  if (!isObject(body)) return fail('invalid-response')
  checkGraphQLErrors(body, 'history')
  if (!isObject(body.data) || !isObject(body.data.coopResult)) return fail('invalid-response')
  const result = body.data.coopResult
  const lists = ['historyGroups', 'historyGroupsOnlyFirst'].filter(key => result[key] !== undefined)
  if (lists.length === 0) return fail('invalid-response')
  const ids = new Set<string>()
  for (const key of lists) {
    const groups = result[key]
    if (!isObject(groups) || !Array.isArray(groups.nodes)) return fail('invalid-response')
    for (const group of groups.nodes) {
      if (!isObject(group) || !isObject(group.historyDetails) || !Array.isArray(group.historyDetails.nodes)) {
        return fail('invalid-response')
      }
      for (const item of group.historyDetails.nodes) {
        if (!isObject(item)) return fail('invalid-response')
        if (!validIdentifier(item.id)) return fail('invalid-id')
        if (!ids.has(item.id) && ids.size >= MAX_HISTORY_IDS) return fail('limit')
        ids.add(item.id)
      }
    }
  }
  return [...ids]
}

// Player IDs are opaque and scoped to each result; validate their presence, not equality across results.
function detailAvailable(body: unknown, expectedID: string): boolean {
  if (!isObject(body)) return fail('invalid-response')
  checkGraphQLErrors(body, 'detail')
  if (!isObject(body.data) || !has(body.data, 'coopHistoryDetail')) return fail('invalid-response')
  const detail = body.data.coopHistoryDetail
  if (detail === null) return false
  if (!isObject(detail)) return fail('invalid-response')
  if (detail.id !== expectedID) return fail('id-mismatch')
  const player = isObject(detail.myResult) ? detail.myResult.player : undefined
  if (!isObject(player) || !validIdentifier(player.id)) return fail('invalid-principal')
  return true
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
      const pair = queriesFor(version)
      const language = typeof res.body.lang === 'string' && res.body.lang ? res.body.lang : headers['accept-language']
      if (!language) throw new Error('missing-context')
      const limit = cfg.settings?.maxResults ?? MAX_RESULTS
      if (typeof limit !== 'number' || !Number.isInteger(limit) || limit < 1 || limit > MAX_RESULTS) {
        throw new Error('invalid-limit')
      }
      const authHeaders = requestHeaders(token, version, language, headers['user-agent'])

      const post = (request: GraphQLRequest) =>
        fetch(ENDPOINT, { method: 'POST', headers: authHeaders, body: JSON.stringify(request) })
      const save = (atPath: string, contents: string) =>
        Interceptor.createFile({ storage: Interceptor.Storage.iCloudDrive, atPath, contents })

      const historyReply = await post(graphqlRequest(pair.history, {}))
      checkStatus(historyReply.status)
      const historyText = await historyReply.text()
      const ids = historyIDs(parseJSON(historyText))
      await save(HISTORY_PATH, historyText)

      const acquired: string[] = []
      const unavailable: string[] = []
      for (const id of ids.slice(0, limit)) {
        const reply = await post(detailRequest(pair, id))
        if (reply.status === 404) { unavailable.push(id); continue }
        checkStatus(reply.status)
        const text = await reply.text()
        if (!detailAvailable(parseJSON(text), id)) { unavailable.push(id); continue }
        // Save the validated response text as received; a failed save stops the chain.
        await save(detailPath(id), text)
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
