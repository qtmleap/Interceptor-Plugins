import { fileURLToPath } from 'node:url'
import { defineConfig, type DefaultTheme } from 'vitepress'
import { loadContext, plainValues, substitute } from './metadata.mts'
import { substituteFrontmatter, tokenPlugin } from './tokens.mts'

const context = loadContext()
const SOURCE = 'https://github.com/' + context.githubRepository

const texts = {
  root: { unconfigured: '未設定' },
  en: { unconfigured: 'not configured' }
}

const textsFor = (relativePath: string) => (relativePath.startsWith('en/') ? texts.en : texts.root)

const pages = ['getting-started', 'authoring', 'api', 'examples', 'publishing', 'devcontainer'] as const

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
  return pages.map((page) => ({ text: labels[locale][page], link: `${prefix}${page}` }))
}

function sidebar(locale: 'root' | 'en'): DefaultTheme.Sidebar {
  const prefix = locale === 'root' ? '/' : '/en/'
  const hooks = [
    ['request.onEnter', 'request-onenter'],
    ['request.onLeave', 'request-onleave'],
    ['response.onEnter', 'response-onenter'],
    ['response.onLeave', 'response-onleave']
  ]
  const items = pages.map((page) => ({
    text: labels[locale][page], link: `${prefix}${page}`,
    ...(page === 'api' ? { items: hooks.map(([text, anchor]) => ({ text, link: `${prefix}api#${anchor}` })) } : {})
  }))
  return [{ text: locale === 'root' ? 'ドキュメント' : 'Documentation', items }]
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
  title: context.name,
  // Keep repository-controlled metadata in an external JS asset, never an inline script.
  metaChunk: true,
  markdown: {
    config: (md) => tokenPlugin(md, context, textsFor)
  },
  transformPageData(pageData) {
    const text = textsFor(pageData.relativePath)
    pageData.frontmatter = substituteFrontmatter(pageData.frontmatter, context, text) as typeof pageData.frontmatter
    const values = plainValues(context, text)
    if (pageData.title) pageData.title = substitute(pageData.title, values)
    if (pageData.description) pageData.description = substitute(pageData.description, values)
  },
  themeConfig: {
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
    server: { fs: { allow: [fileURLToPath(new URL('../..', import.meta.url))] } }
  }
})
