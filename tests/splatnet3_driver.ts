// Exercise the canonical Plugin's pure helpers without duplicating their source.
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const input = JSON.parse(readFileSync(0, 'utf8')) as { fn: string; args: unknown[] }
const names = ['resolveQueries', 'makeHistoryQuery', 'makeDetailQuery', 'observationHashes', 'historyIDs', 'inspectDetail']
if (!names.includes(input.fn)) throw new Error('unknown test function')
const source = readFileSync(new URL('../plugins/splatnet3-salmon/hooks/api.lp1.av5ja.srv.nintendo.net/api/bullet_tokens/POST.ts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.None } }).outputText
const context = vm.createContext({ Interceptor: { attach() {} }, __args: input.args })
vm.runInContext(code, context, { timeout: 1000 })
try {
  const value = vm.runInContext(input.fn + '(...__args)', context, { timeout: 1000 })
  console.log(JSON.stringify({ ok: true, value }))
} catch (e) {
  console.log(JSON.stringify({ ok: false, code: (e as { code?: string }).code ?? 'unexpected' }))
}
