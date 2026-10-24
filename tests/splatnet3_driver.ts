// Exercise the canonical Plugin's pure helpers without duplicating their source.
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { sha256 } from 'js-sha256'
import ts from 'typescript'

const IMPORT = "import { sha256 } from 'js-sha256'\n"
const names = ['queriesFor', 'historyIDs', 'detailAvailable', 'detailPath', 'validIdentifier']
const input = JSON.parse(readFileSync(0, 'utf8')) as { fn: string; args: unknown[] }
if (!names.includes(input.fn)) throw new Error('unknown test function')
const source = readFileSync(new URL('../plugins/splatnet3-salmon/hooks/api.lp1.av5ja.srv.nintendo.net/api/bullet_tokens/POST.ts', import.meta.url), 'utf8')
if (!source.includes(IMPORT)) throw new Error('approved js-sha256 import is missing')
// Only the approved import is removed; the package function is injected in its place.
const code = ts.transpileModule(source.replace(IMPORT, ''), { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.None } }).outputText
const context = vm.createContext({ Interceptor: { attach() {} }, sha256, __args: input.args })
vm.runInContext(code, context, { timeout: 1000 })
try {
  const value = vm.runInContext(input.fn + '(...__args)', context, { timeout: 1000 })
  console.log(JSON.stringify({ ok: true, value }))
} catch (e) {
  console.log(JSON.stringify({ ok: false, code: (e as Error).message }))
}
