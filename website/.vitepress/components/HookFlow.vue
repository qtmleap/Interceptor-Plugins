<script setup lang="ts">
import { withBase } from 'vitepress'

const props = defineProps<{ locale: 'ja' | 'en' }>()
const copy = {
  ja: {
    scroll: "通信の流れとHookの位置。画面が狭い場合は横にスクロールして確認できます",
    alt: "未実装のHook設計を示す図です。クライアントからサーバーへ送るリクエストには1 request.onEnterと2 request.onLeave、サーバーから元のアプリへ返すレスポンスには3 response.onEnterと4 response.onLeaveを設けます。onEnterでは転送前に内容を変更でき、onLeaveでは転送後の後処理を行います。",
    caption: "青いカードは転送前に内容を変更できるHook、破線の矢印は転送後に呼ぶHookを示します。番号は下の説明に対応します。図はHookを呼ぶ位置を示すもので、4つ全体の実行順序や、相手がデータを受信・処理したことを保証するものではありません。狭い画面では横にスクロールして確認できます。"
  },
  en: {
    scroll: 'Traffic and Hook positions. Scroll horizontally on narrow screens',
    alt: 'Unimplemented Hook design. Requests flow from client to server through 1 request.onEnter and 2 request.onLeave; responses flow back through 3 response.onEnter and 4 response.onLeave. onEnter can edit before forwarding; onLeave runs afterward.',
    caption: 'Blue cards can edit content before forwarding; dashed branches show follow-up work after forwarding. Numbers match the sections below. The diagram does not guarantee an overall order for all four hooks, or receipt and processing by the peer. Scroll horizontally on narrow screens.'
  }
}
</script>

<template>
  <figure class="hook-flow">
    <div class="hook-flow-scroll" tabindex="0" :aria-label="copy[props.locale].scroll">
      <img class="hook-flow-light" :src="withBase(`/diagrams/plugin-hooks-${props.locale}-light.svg`)" :alt="copy[props.locale].alt" width="760" height="568">
      <img class="hook-flow-dark" :src="withBase(`/diagrams/plugin-hooks-${props.locale}-dark.svg`)" :alt="copy[props.locale].alt" width="760" height="568">
    </div>
    <figcaption>{{ copy[props.locale].caption }}</figcaption>
  </figure>
</template>

<style>
.hook-flow { max-width: 760px; margin: 24px auto; }
.hook-flow-scroll { overflow-x: auto; border: 1px solid var(--vp-c-divider); border-radius: 16px; }
.hook-flow-scroll img { display: block; width: 100%; min-width: 620px; max-width: none; height: auto; margin: 0; }
.hook-flow-scroll .hook-flow-dark { display: none; }
.dark .hook-flow-scroll .hook-flow-light { display: none; }
.dark .hook-flow-scroll .hook-flow-dark { display: block; }
.hook-flow figcaption { margin-top: 12px; color: var(--vp-c-text-2); font-size: 14px; line-height: 1.7; }
</style>
