---
title: ホーム
lang: ja
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: プラグインを試す・作る・公開する
  tagline: Interceptor PluginはJavaScriptで独自の処理を追加する仕組みです。現在は合成データで処理を試し、署名付きのパッケージとして配布できます。
  actions:
    - theme: brand
      text: テストデータで試す
      link: /getting-started
    - theme: alt
      text: プラグインを書く
      link: /authoring
    - theme: alt
      text: 自分のリポジトリを公開する
      link: /publishing
features:
  - title: 合成データでプレビュー
    details: 同期的なv1の合成プレビューです。Webhookへの送信要求を最大2件返します。現在のプレビューは結果の表示までで、送信や実通信への接続は行いません。
    link: /api
  - title: TypeScriptで開発
    details: src/*.ts とmanifestを編集すると、型チェックと変換を経て読みやすいJavaScriptのパッケージになります。
    link: /authoring
  - title: 署名と信頼
    details: パッケージのハッシュと一覧の署名を検証します。公開鍵の指紋は信頼できる別の経路で照合します。
    link: /getting-started#信頼の確認
  - title: テンプレートから公開
    details: clone後、セットアップで署名鍵・GitHubのSecret・Pagesを設定します。masterへのpush後は、CIが署名して公開します。
    link: /publishing
---

<script setup>
import HookFlow from './.vitepress/components/HookFlow.vue'
</script>

## Interceptor Pluginとは

Interceptorは、アプリとサーバーの間のネットワーク通信を確認するためのアプリです。Interceptor Pluginは、JavaScriptで書いた独自の処理をInterceptorに追加する仕組みです。作者は処理のソースと、名前・バージョン・対象条件などを記すmanifestをパッケージにまとめて配布します。このリポジトリではTypeScriptからJavaScriptを生成します。

現在は、プラグインを取り込み、合成データで処理を試せます。結果のWebhook送信要求は画面に表示されるだけで、配送されません。実際の通信への自動実行や、通信内容の変更にはまだ対応していません。[現在のAPI](api.md#onrequest)と[合成プレビューのサンプル](examples.md#request-summary)から試せます。

今後は、送信するJSONの検索件数を変える、返却するJSONの一部の項目を変更してメンテナンス表示を試す、通信に応じた通知などの後処理を書く使い方を想定しています。以下は、そのためのHTTP Hookの設計です。

## 通信とHookの位置

**図の4つのHookはすべて未実装です。** 現在の合成テスト用の `onRequest` / `onResponse` は、この通信経路で自動的に呼ばれるものではありません。

<HookFlow locale="ja" />

## JSを呼ぶタイミング

リクエストは元のアプリからサーバーへの要求、レスポンスはサーバーから元のアプリへの応答です。Interceptorがホスト・パス・メソッドを照合し、条件に一致した通信のHookだけを呼ぶ設計です。対象条件とHookは [`Interceptor.attach`](api.md#hook-registration) にまとめるため、Hook内で同じ条件を判定し直す必要はありません。

### 1. request.onEnter

リクエストをサーバーへ送る前に呼び、送信内容を変更します。たとえば、JSON本文の検索件数や言語を変更する処理を書きます。[コードとJSONの変更例](api.md#before-request)を参照してください。

### 2. request.onLeave

リクエストをサーバーへ送った後に呼び、送信内容に応じた後処理を行います。引数は送ったリクエストで、サーバーからのレスポンスではありません。送信済みの内容は変更できません。[記述例](api.md#after-request)を参照してください。

### 3. response.onEnter

サーバーのレスポンスを受け取り、元のアプリへ返す前に呼びます。JSON本文を書き換え、サーバーの実装を変えずにメンテナンス表示を試す用途などを想定しています。[コードとJSONの変更例](api.md#before-response)を参照してください。

### 4. response.onLeave

レスポンスを元のアプリへ返した後に呼び、エラーの検知や通知などの後処理を行います。返却済みの内容は変更できません。[記述例](api.md#after-response)を参照してください。

「送信後」「返却後」をどの転送完了で判断するかは未設計です。相手が受信・処理したことまで保証しません。通知の発行方法や、ストリーミング・圧縮・大きな本文・待ち時間の上限も未確定です。

ホーム画面のショートカットなどから、通信の発生を待たずに選んだ処理を実行する機能も検討しています。これは4つの通信Hookとは別の機能案で、現在の合成テストとも異なります。[任意実行](api.md#manual)を参照してください。

## 作成と公開

このサイトは **%%REPOSITORY_NAME%%** の利用者・作者向けガイドです。リポジトリのURLは `%%REPOSITORY_URL%%` です。

- [はじめに](getting-started.md): リポジトリの追加、読み込み、テスト
- [TypeScriptの書き方](authoring.md): ビルド、テスト、バージョン更新
- [APIリファレンス](api.md): manifestのフィールド、フック、権限、バインディング
- [サンプル](examples.md): 実際のソースとmanifest
- [公開](publishing.md): 自分のリポジトリを作って配布する
- [開発コンテナ](devcontainer.md): Linuxでの開発と制限
