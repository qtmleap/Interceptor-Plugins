---
title: ホーム
lang: ja
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: プラグインを試す・作る・公開する
  tagline: Interceptorでサンプルをテストデータで試す手順と、TypeScriptで自分のプラグインを作り、署名付きで配布する方法を案内します。
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

このサイトは **%%REPOSITORY_NAME%%** の利用者・作者向けガイドです。リポジトリのURLは `%%REPOSITORY_URL%%` です。

- [はじめに](getting-started.md): リポジトリの追加、読み込み、テスト
- [TypeScriptの書き方](authoring.md): ビルド、テスト、バージョン更新
- [APIリファレンス](api.md): manifestのフィールド、フック、権限、バインディング
- [サンプル](examples.md): 実際のソースとmanifest
- [公開](publishing.md): 自分のリポジトリを作って配布する
- [開発コンテナ](devcontainer.md): Linuxでの開発と制限
