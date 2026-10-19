---
title: ホーム
lang: ja
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: 通信に合わせてJavaScriptを実行する
  tagline: Interceptor Pluginは、条件に合うリクエストやレスポンスに独自の処理を加える機能です。送信前にJSONを書き換えたり、転送後に処理を実行したりできます。
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
    details: ホスト・パス・メソッドを指定します。条件に一致した通信だけがHookに渡るので、各関数で同じ条件を判定する必要はありません。
    link: /api
  - title: JSONを直接変更
    details: request.onEnterではサーバーへ送るJSON、response.onEnterではクライアントへ返すJSONを変更できます。
    link: /authoring
  - title: Linuxでも開発・配布
    details: BunでTypeScriptをビルドし、Rust製シミュレーターで構文と実行結果を確認できます。パッケージの署名にもXcodeは不要です。
    link: /devcontainer
---

<script setup>
import HookFlow from './.vitepress/components/HookFlow.vue'
</script>

## Interceptor Pluginとは

Interceptorはクライアントとサーバーの間を通る通信を確認するアプリです。プラグインを使うと、その通信にJavaScriptで書いた処理を追加できます。たとえば、検索リクエストの件数を変える、レスポンスのJSONに項目を足す、転送後の内容から結果を組み立てる、といった使い方ができます。

作者は処理のソースとmanifestを1つのパッケージにまとめます。manifestには対象の通信と、読み取り・書き込みに必要な権限を記載します。利用者はソースと権限を確認し、表示された内容を承認してから実通信で使います。

## JavaScriptを呼ぶタイミング

リクエストとレスポンスに、それぞれ`onEnter`と`onLeave`があります。`onEnter`は転送前に内容を変更する処理、`onLeave`は転送後の処理に使います。

<HookFlow locale="ja" />

### request.onEnter

クライアントから受け取ったリクエストを、サーバーへ送る前に呼びます。たとえば`request.body.limit = 5`と書くと、JSON本文の`limit`を変更できます。

### request.onLeave

リクエストの転送が成功した後に呼びます。送った内容を使って結果を作るときに使います。この時点では通信内容を書き換えられません。

### response.onEnter

サーバーから受け取ったレスポンスを、クライアントへ返す前に呼びます。たとえば`response.body.maintenance = true`と書くと、JSON本文に項目を追加できます。

### response.onLeave

レスポンスの転送が成功した後に呼びます。クライアントへ返した内容を使って結果を作ります。この時点では通信内容を書き換えられません。

具体的なコードは[APIリファレンス](api.md#request-onenter)、変更前後のJSONは[プラグインを書く](authoring.md#jsonを変更する)で確認できます。Hookが返すWebhook送信要求は、合成テストの結果欄で確認するためのデータです。実通信では戻り値を保存・送信しません。

## 作成から公開まで

このサイトは **%%REPOSITORY_NAME%%** の利用者・作者向けガイドです。配布用URLは`%%REPOSITORY_URL%%`です。

- [はじめに](getting-started.md): アプリに読み込み、テストして承認する
- [プラグインを書く](authoring.md): TypeScript、JSONの変更、シミュレーター
- [API](api.md): 4つのHook、対象条件、権限
- [サンプル](examples.md): ソースとmanifest
- [公開](publishing.md): 署名して配布する
- [開発コンテナ](devcontainer.md): Linuxで開発する
