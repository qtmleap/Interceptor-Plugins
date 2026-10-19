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

## Interceptor Pluginとは

Interceptorはアプリとサーバーの間のネットワーク通信を確認するためのアプリです。Interceptor Pluginは、JavaScriptで書いた独自の処理を追加する機能です。作者は処理のソースと、プラグイン名・バージョン・対象条件などを記載したmanifestをパッケージにまとめて配布します。このリポジトリではTypeScriptでソースを書き、JavaScriptに変換してパッケージを作ります。

現在はプラグインを読み込み、テスト用に用意した合成データで動作を確認できます。結果として返されたWebhookへの送信要求は画面に表示されるだけで、実際には送信されません。実際の通信をきっかけに処理を自動実行する機能や、通信内容を変更する機能は未実装です。[現在のAPI](api.md#onrequest)と[合成プレビューのサンプル](examples.md#request-summary)から試せます。

## 作成と公開

このサイトは **%%REPOSITORY_NAME%%** の利用者・作者向けガイドです。リポジトリのURLは `%%REPOSITORY_URL%%` です。

- [はじめに](getting-started.md): リポジトリの追加、読み込み、テスト
- [TypeScriptの書き方](authoring.md): ビルド、テスト、バージョン更新
- [APIリファレンス](api.md): manifestのフィールド、フック、権限、バインディング
- [サンプル](examples.md): 実際のソースとmanifest
- [公開](publishing.md): 自分のリポジトリを作って配布する
- [開発コンテナ](devcontainer.md): Linuxでの開発と公開
