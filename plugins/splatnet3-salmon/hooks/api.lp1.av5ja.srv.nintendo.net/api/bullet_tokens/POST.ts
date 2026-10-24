// SplatNet 3 Salmon Run acquisition. Requests are defined only in this file; results are stored with Interceptor.createFile.
import { sha256 } from 'js-sha256'

type QueryPair = { history: string; detail: string }
// Only the response fields this hook reads; everything else is saved unchanged and never inspected.
type HistoryList = { nodes?: { historyDetails?: { nodes?: { id?: unknown }[] } }[] }
type GraphQLBody = {
  errors?: unknown
  data?: {
    coopResult?: { historyGroups?: HistoryList; historyGroupsOnlyFirst?: HistoryList }
    coopHistoryDetail?: { id?: unknown } | null
  }
}

const ENDPOINT = 'https://api.lp1.av5ja.srv.nintendo.net/api/graphql'
const HISTORY_PATH = 'Salmon Run/history.json'
const MAX_RESULTS = 50

// Query IDs are pinned to the captured web-view version; provenance: docs/development/splatnet3-queries.json.
const QUERIES = new Map<string, QueryPair>([
  ['4.0.0-091d4283', {
    history: '0f8c33970a425683bb1bdecca50a0ca4fb3c3641c0b2a1237aedfde9c0cb2b8f',
    detail: '824a1e22c4ad4eece7ad94a9a0343ecd76784be4f77d8f6f563c165afc8cf602',
  }],
  ['10.0.0-d15503c4', {
    history: 'e11a8cf2c3de7348495dea5cdcaa25e0c153541c4ed63f044b6c174bc5b703df',
    detail: 'f2d55873a9281213ae27edc171e2b19131b3021a2ae263757543cdd3bf015cc8',
  }],
])

function fail(code: string): never {
  throw new Error(code)
}

// Result IDs are opaque; only non-empty strings can be requested.
const validIdentifier = (v: unknown): v is string => typeof v === 'string' && v !== ''

function queriesFor(version: string): QueryPair {
  if (version === '') return fail('missing-context')
  return QUERIES.get(version) ?? fail('unsupported-version')
}

// Result IDs may be long or contain slashes, so file names use a fixed-length digest of the UTF-8 ID.
const detailPath = (id: string): string => 'Salmon Run/details/' + sha256(id) + '.json'

// Parse only for acquisition; the original response text is what gets saved.
function parseJSON(text: string): GraphQLBody | null {
  try { return JSON.parse(text) } catch (e) { return fail('invalid-response') }
}

// 401/403 mean the token expired; it is never retried.
function checkStatus(status: number): void {
  if (status === 401 || status === 403) fail('recapture')
  if (status < 200 || status > 299) fail('http')
}

// Any non-null `errors` member is a failure; an empty array contains no errors.
function checkGraphQLErrors(body: GraphQLBody | null, context: 'history' | 'detail'): void {
  const errors = body?.errors
  if (errors === undefined || errors === null) return
  if (!Array.isArray(errors)) fail('graphql')
  if (errors.length === 0) return
  const queryRejected = context === 'detail' && errors.some(error =>
    error?.message === 'PersistedQueryNotFound' || error?.extensions?.code === 'PERSISTED_QUERY_NOT_FOUND')
  fail(queryRejected ? 'query-rejected' : 'graphql')
}

// A missing history list is malformed; an empty one is a valid history with nothing to fetch.
function historyIDs(body: GraphQLBody | null): string[] {
  checkGraphQLErrors(body, 'history')
  const result = body?.data?.coopResult
  const lists = [result?.historyGroups, result?.historyGroupsOnlyFirst].filter(list => Array.isArray(list?.nodes))
  if (lists.length === 0) return fail('invalid-response')
  const groups = lists.flatMap(list => list?.nodes ?? [])
  const details = groups.flatMap(group => group?.historyDetails?.nodes ?? [])
  return [...new Set(details.map(item => item?.id).filter(validIdentifier))]
}

// The detail ID must match the request so the saved file is the one its name says.
function detailAvailable(body: GraphQLBody | null, expectedID: string): boolean {
  checkGraphQLErrors(body, 'detail')
  const detail = body?.data?.coopHistoryDetail
  if (detail === undefined) return fail('invalid-response')
  if (detail === null) return false
  if (detail.id !== expectedID) return fail('id-mismatch')
  return true
}

Interceptor.attach({
  response: {
    async onLeave(res, cfg) {
      if (res.status !== 201) return
      const body = res.body as { bulletToken?: unknown; lang?: unknown } | null
      const token = body?.bulletToken
      if (typeof token !== 'string' || token === '') return
      const headers = res.request.headers || {}
      const version = headers['x-web-view-ver'] || ''
      const pair = queriesFor(version)
      const language = typeof body?.lang === 'string' && body.lang ? body.lang : headers['accept-language']
      if (!language) throw new Error('missing-context')
      const limit = cfg.settings?.maxResults ?? MAX_RESULTS
      if (typeof limit !== 'number' || !Number.isInteger(limit) || limit < 1 || limit > MAX_RESULTS) {
        throw new Error('invalid-limit')
      }
      const userAgent = headers['user-agent']
      // Forward only the required headers; login cookies stay out of GraphQL requests.
      const authHeaders = {
        authorization: 'Bearer ' + token,
        'content-type': 'application/json',
        'x-web-view-ver': version,
        'accept-language': language,
        'x-requested-with': 'XMLHttpRequest',
        ...(userAgent ? { 'user-agent': userAgent } : {}),
      }

      const post = (hash: string, variables: { [name: string]: string } = {}) =>
        fetch(ENDPOINT, { method: 'POST', headers: authHeaders, body: JSON.stringify({
          variables, extensions: { persistedQuery: { version: 1, sha256Hash: hash } },
        }) })
      const save = (atPath: string, contents: string) =>
        Interceptor.createFile({ storage: Interceptor.Storage.iCloudDrive, atPath, contents })

      const historyReply = await post(pair.history)
      checkStatus(historyReply.status)
      const historyText = await historyReply.text()
      const ids = historyIDs(parseJSON(historyText))
      await save(HISTORY_PATH, historyText)

      const counts = { acquired: 0, unavailable: 0 }
      for (const id of ids.slice(0, limit)) {
        const reply = await post(pair.detail, { coopHistoryDetailId: id })
        if (reply.status === 404) { counts.unavailable += 1; continue }
        checkStatus(reply.status)
        const text = await reply.text()
        if (!detailAvailable(parseJSON(text), id)) { counts.unavailable += 1; continue }
        // Save the original response; a failed save stops the chain.
        await save(detailPath(id), text)
        counts.acquired += 1
      }
      // Existing diagnostic action; not an HTTP send. Never include the token or result bodies.
      return { actions: [{
        type: 'webhook', endpointId: '8B71B789-357C-44D8-AF3A-1D8192234BB5',
        json: { version, ...counts, remaining: Math.max(0, ids.length - limit) },
      }] }
    },
  },
})
