<script setup lang="ts">
import { withBase } from 'vitepress'

const props = defineProps<{ locale: 'ja' | 'en' }>()
const copy = {
  ja: {
    alt: 'クライアント、Interceptor、サーバーの通信経路。request.onEnterはサーバーへの送信前、request.onLeaveは送信成功後。response.onEnterはクライアントへの返却前、response.onLeaveは返却成功後に呼ばれます。',
    caption: '青いHookではJSON本文を変更できます。破線のHookは転送成功後の処理です。転送成功は、相手が受信・処理したことまで保証しません。',
    scroll: '通信とHookの図。狭い画面では横にスクロールできます',
  },
  en: {
    alt: 'Client, Interceptor and server. request.onEnter runs before forwarding upstream and request.onLeave after successful forwarding. response.onEnter runs before forwarding downstream and response.onLeave after successful forwarding.',
    caption: 'Blue hooks can edit the JSON body. Dashed hooks run after successful local forwarding, which does not guarantee receipt or processing by the peer.',
    scroll: 'Traffic and hook diagram. Scroll horizontally on narrow screens',
  },
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
.hook-flow { margin: 28px 0; }
.hook-flow-scroll { overflow-x: auto; border: 1px solid var(--vp-c-divider); border-radius: 12px; background: var(--vp-c-bg); }
.hook-flow-scroll img { display: block; width: 100%; min-width: 620px; max-width: 760px; height: auto; margin: 0 auto; }
.hook-flow-scroll .hook-flow-dark { display: none; }
.dark .hook-flow-scroll .hook-flow-light { display: none; }
.dark .hook-flow-scroll .hook-flow-dark { display: block; }
.hook-flow figcaption { color: var(--vp-c-text-2); margin-top: 12px; font-size: 14px; line-height: 1.7; }
</style>
