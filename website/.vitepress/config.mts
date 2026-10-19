import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, type DefaultTheme } from 'vitepress'
import { loadContext, plainValues, substitute } from './metadata.mts'
import { substituteFrontmatter, tokenPlugin } from './tokens.mts'

const context = loadContext()
const SOURCE = 'https://github.com/' + context.githubRepository
const siteTitle = context.githubRepository === 'qtmleap/Interceptor-Plugins' ? 'Interceptor Plugins' : context.name

const texts = {
  root: { unconfigured: '未設定' },
  en: { unconfigured: 'not configured' }
}

const textsFor = (relativePath: string) => (relativePath.startsWith('en/') ? texts.en : texts.root)

const labels = {
  root: {
    'getting-started': 'はじめに',
    authoring: '作成',
    api: 'API',
    examples: 'サンプル',
    publishing: '公開',
    devcontainer: '開発コンテナー'
  },
  en: {
    'getting-started': 'Getting started',
    authoring: 'Authoring',
    api: 'API',
    examples: 'Examples',
    publishing: 'Publishing',
    devcontainer: 'Dev container'
  }
} as const

function nav(locale: 'root' | 'en'): DefaultTheme.NavItem[] {
  const prefix = locale === 'root' ? '/' : '/en/'
  return [
    { text: locale === 'root' ? 'ガイド' : 'Guide', link: `${prefix}getting-started`, activeMatch: '/(getting-started|authoring|examples|publishing|devcontainer)' },
    { text: locale === 'root' ? 'リファレンス' : 'Reference', link: `${prefix}api`, activeMatch: '/api' }
  ]
}

function sidebar(locale: 'root' | 'en'): DefaultTheme.Sidebar {
  const prefix = locale === 'root' ? '/' : '/en/'
  const ja = locale === 'root'
  const page = (name: keyof typeof labels.root): DefaultTheme.SidebarItem => ({ text: labels[locale][name], link: `${prefix}${name}` })
  const referenceLink = (text: string, anchor: string): DefaultTheme.SidebarItem => ({ text, link: `${prefix}api#${encodeURIComponent(anchor)}` })
  const hooks = [
    ['request.onEnter', 'request-onenter'],
    ['request.onLeave', 'request-onleave'],
    ['response.onEnter', 'response-onenter'],
    ['response.onLeave', 'response-onleave']
  ]
  const guide: DefaultTheme.SidebarItem[] = [
    { text: ja ? '導入' : 'Introduction', items: [page('getting-started')] },
    { text: ja ? 'プラグイン' : 'Plugins', items: [page('authoring'), page('examples')] },
    { text: ja ? '開発と公開' : 'Development and publishing', items: [page('devcontainer'), page('publishing')] },
    { items: [{ text: ja ? 'APIリファレンス' : 'API reference', link: `${prefix}api` }] }
  ]
  const reference: DefaultTheme.SidebarItem[] = [
    { text: ja ? 'リファレンス' : 'Reference', items: [
      { text: ja ? '概要' : 'Overview', link: `${prefix}api` },
      referenceLink('Interceptor.attach', 'interceptor-attach'),
      referenceLink(ja ? '対象条件' : 'Matching', ja ? '対象条件' : 'matching')
    ] },
    { text: 'Hook', items: hooks.map(([text, anchor]) => referenceLink(text, anchor)) },
    { text: ja ? '設定と制限' : 'Configuration and limits', items: [
      referenceLink(ja ? 'manifestと権限' : 'Manifest and permissions', ja ? 'manifestと権限' : 'manifest-and-permissions'),
      referenceLink(ja ? '実行条件と制限' : 'Execution and limits', ja ? '実行条件と制限' : 'execution-and-limits'),
      referenceLink(ja ? '型宣言' : 'Types', ja ? '型宣言' : 'types')
    ] },
    { items: [{ text: ja ? 'ガイド' : 'Guide', link: `${prefix}getting-started` }] }
  ]
  // Flat routes have equal depth; keep the specific API prefix before the guide fallback.
  return { [`${prefix}api`]: reference, [prefix]: guide }
}

const searchTranslations = {
  root: {
    button: { buttonText: '検索', buttonAriaLabel: '検索' },
    modal: {
      displayDetails: '詳細を表示',
      resetButtonTitle: '検索条件をクリア',
      backButtonTitle: '検索を閉じる',
      noResultsText: '一致する結果がありません',
      footer: { selectText: '選択', selectKeyAriaLabel: 'Enter', navigateText: '移動', navigateUpKeyAriaLabel: '上矢印', navigateDownKeyAriaLabel: '下矢印', closeText: '閉じる', closeKeyAriaLabel: 'Esc' }
    }
  }
}

export default defineConfig({
  outDir: fileURLToPath(new URL('../../build/docs', import.meta.url)),
  cacheDir: fileURLToPath(new URL('../../build/vitepress-cache', import.meta.url)),
  base: context.base,
  cleanUrls: false,
  lastUpdated: false,
  srcExclude: ['**/node_modules/**'],
  title: siteTitle,
  head: [['link', { rel: 'icon', type: 'image/png', href: `${context.base}images/interceptor.png` }]],
  // Keep repository-controlled metadata in an external JS asset, never an inline script.
  metaChunk: true,
  markdown: {
    config: (md) => tokenPlugin(md, context, textsFor)
  },
  transformPageData(pageData) {
    const text = textsFor(pageData.relativePath)
    pageData.frontmatter = substituteFrontmatter(pageData.frontmatter, { ...context, name: siteTitle }, text) as typeof pageData.frontmatter
    const values = plainValues(context, text)
    if (pageData.title) pageData.title = substitute(pageData.title, values)
    if (pageData.description) pageData.description = substitute(pageData.description, values)
  },
  themeConfig: {
    logo: { src: '/images/interceptor.png', alt: '' },
    search: {
      provider: 'local',
      options: {
        detailedView: true,
        locales: { root: { translations: searchTranslations.root } }
      }
    },
    socialLinks: [{ icon: 'github', link: SOURCE, ariaLabel: 'GitHub' }]
  },
  locales: {
    root: {
      label: '日本語',
      lang: 'ja',
      description: 'Interceptor 用プラグインリポジトリの作り方と公開方法',
      themeConfig: {
        nav: nav('root'),
        sidebar: sidebar('root'),
        outline: { label: 'このページの内容' },
        docFooter: { prev: '前のページ', next: '次のページ' },
        darkModeSwitchLabel: '外観',
        lightModeSwitchTitle: 'ライトテーマに切り替え',
        darkModeSwitchTitle: 'ダークテーマに切り替え',
        sidebarMenuLabel: 'メニュー',
        returnToTopLabel: 'トップに戻る',
        langMenuLabel: '言語を変更',
        skipToContentLabel: '本文へスキップ',
        notFound: {
          title: 'ページが見つかりません',
          quote: 'URL が変更されたか、ページが存在しない可能性があります。',
          linkLabel: 'ホームへ戻る',
          linkText: 'ホームへ戻る',
          code: '404'
        }
      }
    },
    en: {
      label: 'English',
      lang: 'en',
      link: '/en/',
      description: 'How to build and publish a plugin repository for Interceptor',
      themeConfig: {
        nav: nav('en'),
        sidebar: sidebar('en')
      }
    }
  },
  vite: {
    plugins: [tailwindcss()],
    server: { fs: { allow: [fileURLToPath(new URL('../..', import.meta.url))] } }
  }
})
