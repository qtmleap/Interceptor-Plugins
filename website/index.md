---
title: ホーム
lang: ja
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: 通信に合わせてJavaScriptを実行する
  tagline: Interceptor Pluginは、通信にJavaScriptの処理を追加する機能です。転送前のJSON変更や、転送後の処理をプラグインとしてまとめられます。
  actions:
    - theme: brand
      text: プラグインを書く
      link: /authoring
    - theme: alt
      text: アプリで試す
      link: /getting-started
    - theme: alt
      text: 公開する
      link: /publishing
features:
  - title: 条件に合う通信を処理
    details: ホスト・パス・メソッドで、処理する通信を指定します。
    link: /api
  - title: JSONを直接変更
    details: 転送前に、リクエストやレスポンスのJSON本文を書き換えます。
    link: /authoring
  - title: Linuxでも開発・配布
    details: BunとRust製シミュレーターで開発できます。署名にXcodeは不要です。
    link: /devcontainer
---

<script setup>
import HookFlow from './.vitepress/components/HookFlow.vue'
</script>

## JavaScriptを呼ぶタイミング

転送前は`onEnter`、転送成功後は`onLeave`で処理します。

<HookFlow locale="ja" />

コードの例は[作成ガイド](authoring.md)、各Hookの仕様は[APIリファレンス](api.md)で確認できます。
