import type MarkdownIt from 'markdown-it'
import type Token from 'markdown-it/lib/token.mjs'
import { escapeText, plainValues, substitute, TOKEN, type DocsContext, type Texts, type Token as MetaToken } from './metadata.mts'

type Values = Record<MetaToken, string>

const NAME = '%%REPOSITORY_NAME%%'

// markdown-it normalizes percent signs in link targets before this rule runs.
const restoreLinkTokens = (value: string) => value.replace(
  /%25%25(REPOSITORY_NAME|REPOSITORY_URL|FINGERPRINT|GITHUB_REPOSITORY|BUN_VERSION)%25%25/g,
  '%%$1%%'
)

// Substitute metadata after Markdown parsing so values can never create Markdown, HTML or Vue syntax:
// inline text becomes escaped HTML entities, code and links receive the literal value.
export function tokenPlugin(md: MarkdownIt, context: DocsContext, textsFor: (relativePath: string) => Texts) {
  const has = (value: string | null | undefined) => !!value && value.includes('%%')

  const replaceText = (values: Values, token: Token, TokenClass: new (type: string, tag: string, nesting: 0) => Token): Token[] => {
    // split() with one capture group yields [text, token, text, token, ...]
    const parts = token.content.split(new RegExp(TOKEN.source, 'g'))
    const out: Token[] = []
    parts.forEach((part, index) => {
      if (index % 2 === 0) {
        if (!part) return
        const text = new TokenClass('text', '', 0)
        text.content = part
        out.push(text)
      } else {
        const html = new TokenClass('html_inline', '', 0)
        html.content = escapeText(values[part as MetaToken])
        out.push(html)
      }
    })
    return out
  }

  md.core.ruler.push('interceptor_metadata', (state) => {
    const relativePath = (state.env as { relativePath?: string } | undefined)?.relativePath ?? ''
    const values = plainValues(context, textsFor(relativePath))
    const TokenClass = state.Token as unknown as new (type: string, tag: string, nesting: 0) => Token
    for (const block of state.tokens) {
      if (block.type === 'fence' || block.type === 'code_block') {
        if (has(block.content)) block.content = substitute(block.content, values)
        if (has(block.info)) block.info = substitute(block.info, values)
        continue
      }
      if (block.type === 'html_block' && has(block.content)) {
        throw new Error('Metadata tokens are not supported inside raw HTML blocks')
      }
      if (!block.children) continue
      const children: Token[] = []
      for (const child of block.children) {
        if (child.type === 'text' && has(child.content)) {
          children.push(...replaceText(values, child, TokenClass))
        } else if (child.type === 'code_inline' && has(child.content)) {
          child.content = substitute(child.content, values)
          children.push(child)
        } else if (child.type === 'html_inline' && has(child.content)) {
          throw new Error('Metadata tokens are not supported inside raw HTML')
        } else {
          for (const attr of child.attrs ?? []) {
            attr[1] = restoreLinkTokens(attr[1])
            if (!has(attr[1])) continue
            if (attr[1].includes(NAME) && (attr[0] === 'href' || attr[0] === 'src')) {
              throw new Error('The repository name cannot be used in a link target')
            }
            if (attr[0] === 'href' || attr[0] === 'src' || attr[0] === 'title' || attr[0] === 'alt') {
              attr[1] = substitute(attr[1], values)
            }
          }
          if (child.type === 'image' && has(child.content)) child.content = substitute(child.content, values)
          children.push(child)
        }
      }
      block.children = children
    }
  })
}

// Only top-level page titles/descriptions are plain text; nested hero/feature text uses HTML.
const PLAIN_KEYS = new Set(['title', 'titleTemplate', 'description'])
const LINK_KEYS = new Set(['link'])

export function substituteFrontmatter(data: unknown, context: DocsContext, texts: Texts, key = '', depth = 0): unknown {
  const values = plainValues(context, texts)
  if (typeof data === 'string') {
    if (!data.includes('%%')) return data
    if (depth === 1 && PLAIN_KEYS.has(key)) return substitute(data, values)
    if (LINK_KEYS.has(key)) {
      if (data.includes(NAME)) throw new Error('The repository name cannot be used in a link target')
      return substitute(data, values)
    }
    return substitute(data, values, escapeText)
  }
  if (Array.isArray(data)) return data.map((item) => substituteFrontmatter(item, context, texts, key, depth + 1))
  if (data && typeof data === 'object') {
    return Object.fromEntries(Object.entries(data).map(([k, v]) => [k, substituteFrontmatter(v, context, texts, k, depth + 1)]))
  }
  return data
}
