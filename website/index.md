---
title: ホーム
lang: ja
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: プラグインを試す・作る・公開する
  tagline: Interceptor Pluginではテスト用の通信データを使ってJavaScriptの処理を試せます。作成した処理は署名付きパッケージとして配布できます。
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
    details: テスト用の通信データでスクリプトを実行し、Webhookへの送信要求を最大2件表示します。実際の送信や、実通信を対象とした処理は行いません。同期実行に対応したv1のプレビューです。
    link: /api
  - title: TypeScriptで開発
    details: src/*.ts とmanifestを編集してビルドすると、型チェックとJavaScriptへの変換を経て、読みやすいソースを含むパッケージが生成されます。
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

Interceptorはアプリとサーバーの間のネットワーク通信を確認するためのアプリです。Interceptor PluginはJavaScriptで書いた独自の処理を追加するための機能です。作者は処理のソースと、プラグイン名・バージョン・対象条件などを記すmanifestをパッケージにまとめて配布します。このリポジトリではTypeScriptでソースを書き、JavaScriptに変換してパッケージを作ります。

現在はプラグインを読み込み、テスト用の通信データである合成データを使って動作を確認できます。結果として返されたWebhookへの送信要求は画面に表示されるだけで、実際には送信されません。実際の通信に合わせて処理を自動実行したり、通信内容を変更したりする機能は未実装です。[現在のAPI](api.md#onrequest)と[合成プレビューのサンプル](examples.md#request-summary)から試せます。

今後は送信するJSONの検索件数を変えたり、返却するJSONの一部を書き換えてメンテナンス表示を試したりする用途を想定しています。通信内容に応じて通知するなどの後処理も検討しています。以下ではこれらの処理を記述するためのHTTP Hookの設計を説明します。

## 通信とHookの位置

**図の4つのHookはすべて未実装です。** 現在の合成テスト用の `onRequest` / `onResponse` が、この通信経路で自動的に呼ばれることはありません。

<HookFlow locale="ja" />

## JSを呼ぶタイミング

リクエストは元のアプリからサーバーへの要求、レスポンスはサーバーから元のアプリへの応答です。Interceptorが通信のホスト・パス・メソッドを確認し、条件に一致した場合だけHookを呼ぶ設計です。対象条件とHookを [`Interceptor.attach`](api.md#hook-registration) にまとめて指定するので、Hook内で同じ条件を判定し直す必要はありません。

### 1. request.onEnter

リクエストをサーバーへ送る前にInterceptorが呼ぶHookです。JSON本文の検索件数や言語など、送信内容を変更する処理をここに書きます。[コードとJSONの変更例](api.md#before-request)を参照してください。

### 2. request.onLeave

リクエストをサーバーへ送った後にInterceptorが呼ぶHookです。送信内容に応じた後処理をここに書きます。引数は送ったリクエストで、サーバーからのレスポンスではありません。送信済みの内容は変更できません。[記述例](api.md#after-request)を参照してください。

### 3. response.onEnter

サーバーからレスポンスを受け取り、元のアプリへ返す前にInterceptorが呼ぶHookです。返却するJSON本文を書き換え、サーバーの実装を変えずにメンテナンス表示を試す用途などを想定しています。[コードとJSONの変更例](api.md#before-response)を参照してください。

### 4. response.onLeave

レスポンスを元のアプリへ返した後にInterceptorが呼ぶHookです。エラーの検知や通知などの後処理をここに書きます。返却済みの内容は変更できません。[記述例](api.md#after-response)を参照してください。

どの時点で転送を完了とみなし、「送信後」「返却後」と判断するかは未設計です。相手がデータを受信・処理したことまでは保証しません。通知の発行方法のほか、ストリーミングや圧縮された本文、大きな本文の扱い、処理を待つ時間の上限も未確定です。

ホーム画面のショートカットなどから、通信の発生を待たずに選んだ処理を実行する機能も検討しています。これは4つの通信Hookとは別の機能案で、現在の合成テストとも異なります。[任意実行](api.md#manual)を参照してください。

## 作成と公開

このサイトは **%%REPOSITORY_NAME%%** の利用者・作者向けガイドです。リポジトリのURLは `%%REPOSITORY_URL%%` です。

- [はじめに](getting-started.md): リポジトリの追加、読み込み、テスト
- [TypeScriptの書き方](authoring.md): ビルド、テスト、バージョン更新
- [APIリファレンス](api.md): manifestのフィールド、フック、権限、バインディング
- [サンプル](examples.md): 実際のソースとmanifest
- [公開](publishing.md): 自分のリポジトリを作って配布する
- [開発コンテナ](devcontainer.md): Linuxでの開発と制限
