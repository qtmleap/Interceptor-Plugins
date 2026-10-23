// Offline transport fixture; the generated Plugin itself is evaluated unchanged.
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const input = JSON.parse(readFileSync(0, 'utf8'))
const source = readFileSync(input.source, 'utf8')
const code = input.source.endsWith('.ts')
  ? ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.None } }).outputText
  : source
let hooks: any
const requests: any[] = []
const replies = input.replies ?? []
const saves: { storage: string; path: string; contents: string; failed?: boolean }[] = []
const context = vm.createContext({
  Interceptor: {
    attach(value: any) { hooks = value },
    Storage: { local: 'local', iCloudDrive: 'icloud' },
    async createFile(options: { storage: string; atPath: string; contents: string | Uint8Array }) {
      const failed = input.saveFailAt === saves.length + 1
      if (typeof options.contents !== 'string') throw new Error('unexpected-binary')
      saves.push({ storage: options.storage, path: options.atPath, contents: options.contents, ...(failed ? { failed } : {}) })
      if (failed) throw new Error('save-failed')
    },
  },
  async fetch(url: string, init: any) {
    requests.push({ url, ...init })
    const reply = replies[requests.length - 1]
    if (!reply) throw new Error('unexpected-request')
    return {
      status: reply.status, ok: reply.status >= 200 && reply.status < 300,
      async text() { return typeof reply.body === 'string' ? reply.body : JSON.stringify(reply.body) },
      async json() { return typeof reply.body === 'string' ? JSON.parse(reply.body) : reply.body },
    }
  },
})
vm.runInContext(code, context, { timeout: 1000 })
try {
  const result = await hooks.response.onLeave(input.response, { endpoints: {}, settings: input.settings ?? {} })
  console.log(JSON.stringify({ ok: true, result: result ?? null, requests, saves }))
} catch (e) {
  console.log(JSON.stringify({ ok: false, code: (e as Error).message, requests, saves }))
}
