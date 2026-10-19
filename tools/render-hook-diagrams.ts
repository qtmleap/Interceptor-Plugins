// D2 is needed only to regenerate the checked-in SVGs, never to build the SDK/site.
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'

const root = resolve(import.meta.dir, '..')
const inputs = ['docs/diagrams/http-hooks.d2', 'tools/render-hook-diagrams.ts']
const manifestPath = resolve(root, 'docs/diagrams/generated.json')
const sha = (bytes: Uint8Array) => createHash('sha256').update(bytes).digest('hex')
const bytes = async (path: string) => new Uint8Array(await Bun.file(resolve(root, path)).arrayBuffer())
const inputHashes = Object.fromEntries(await Promise.all(inputs.map(async (path) => [path, sha(await bytes(path))])))
const labels = {
  ja: { CLIENT: 'クライアント', SERVER: 'サーバー', REQUEST: 'リクエスト', SEND: '変更後のリクエストを送信', RETURN: '変更後のレスポンスを返却', RESPONSE: 'レスポンス', BEFORE_REQUEST: '送信前にJSONを変更', AFTER_REQUEST: '送信成功後の処理', BEFORE_RESPONSE: '返却前にJSONを変更', AFTER_RESPONSE: '返却成功後の処理' },
  en: { CLIENT: 'Client', SERVER: 'Server', REQUEST: 'Request', SEND: 'Forward the modified request', RETURN: 'Forward the modified response', RESPONSE: 'Response', BEFORE_REQUEST: 'Edit JSON before forwarding', AFTER_REQUEST: 'After successful forwarding', BEFORE_RESPONSE: 'Edit JSON before forwarding', AFTER_RESPONSE: 'After successful forwarding' },
} as const
const outputs = Object.keys(labels).flatMap((locale) => ['light', 'dark'].map((theme) => `website/public/diagrams/plugin-hooks-${locale}-${theme}.svg`))

if (process.argv.includes('--check')) {
  const expected = await Bun.file(manifestPath).json()
  if (JSON.stringify(expected.inputs) !== JSON.stringify(inputHashes)) throw new Error('Diagram inputs changed; regenerate with D2 0.9.0')
  for (const path of outputs) if (expected.outputs[path] !== sha(await bytes(path))) throw new Error(`Diagram differs: ${path}`)
  console.log('D2 sources and generated diagrams match')
} else {
  const version = Bun.spawnSync(['d2', '--version'], { stdout: 'pipe', stderr: 'pipe' })
  if (version.exitCode !== 0 || new TextDecoder().decode(version.stdout).trim() !== 'v0.9.0') throw new Error('Regeneration requires D2 0.9.0')
  const template = await Bun.file(resolve(root, inputs[0]!)).text()
  for (const [locale, values] of Object.entries(labels)) {
    for (const theme of ['light', 'dark']) {
      const palette = { ...values, ACCENT: theme === 'dark' ? '#9dc0ff' : '#245bba', NEUTRAL: theme === 'dark' ? '#b1bac7' : '#586577' }
      const source = Object.entries(palette).reduce((text, [key, value]) => text.replaceAll(`@@${key}@@`, value), template)
      const rendered = Bun.spawnSync(['d2', '--theme', theme === 'dark' ? '200' : '0', '--pad', '24', '--omit-version', '--salt', `plugin-hooks-${locale}-${theme}`, '-', '-'], { stdin: new TextEncoder().encode(source), stdout: 'pipe', stderr: 'pipe' })
      if (rendered.exitCode !== 0) throw new Error(new TextDecoder().decode(rendered.stderr))
      // Use the reader's system fonts; do not redistribute D2's embedded fonts.
      const svg = new TextDecoder().decode(rendered.stdout)
        .replace(/@font-face\s*\{[^}]*\}/g, '')
        .replace(/font-family:\s*"?d2-[^;}]+/g, 'font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif')
      if (/<script\b|<foreignObject\b|https?:\/\/[^" ]+\.(?:woff|ttf)/i.test(svg)) throw new Error('Diagram contains unexpected active or remote content')
      await Bun.write(resolve(root, `website/public/diagrams/plugin-hooks-${locale}-${theme}.svg`), svg)
    }
  }
  const hashes = Object.fromEntries(await Promise.all(outputs.map(async (path) => [path, sha(await bytes(path))])))
  await Bun.write(manifestPath, JSON.stringify({ generator: 'D2 0.9.0', inputs: inputHashes, outputs: hashes }, null, 2) + '\n')
}
