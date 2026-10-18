---
title: APIリファレンス
lang: ja
---

# APIリファレンス

## 同期v1の合成プレビュー

フックは同期的に呼ばれ、`{ actions: [...] }` を返します。`actions` は最大2件のWebhook intentです。これらは表示されるだけで、送信されません。実キャプチャへの接続やバックグラウンド実行もありません。型は作成の補助で、入力検証や実行権限の付与ではありません。制限と権限はアプリが実行時に検証します。

## 型宣言

<<< ../types/interceptor.d.ts{ts}

## manifestのフィールド

実際のmanifestは [サンプル](examples.md) にあります。

| フィールド | 内容 |
|---|---|
| `schemaVersion` | 常に `1` |
| `id` | プラグインのUUID。公開後は変えません |
| `name` / `version` | 表示名と、変更ごとに上げるバージョン |
| `subscriptions` | `phase`（`request.headers`・`request.completed`・`response.headers`・`response.completed`）と `match` |
| `read` | フックが読める情報の権限（grants） |
| `endpointBindings` | Webhook送信先の名前 |
| `settings` | 設定値（サンプルでは空） |

`match` には `hosts`、`methods`、`path`、`status` を指定できます。`path` は `{ "kind": "exact", "value": "/api/items" }` または `{ "kind": "prefix", "value": "/api/" }`、`status` は `min`/`max` の範囲です。合成テストでは `match` が適用されないため、フック内でも同じ条件を確認してください。

## フック

- `onRequest(event, config)`: request系フェーズ
- `onResponse(event, config)`: response系フェーズ

`event.request` / `event.response` の任意のプロパティは、入力と読み取り権限に依存して存在します。常に存在確認をしてください。

## 読み取り権限（grants）

`read` で必要なものだけを宣言します。

- `metadata`: `method`、`host`、`path`、`status` など
- `headers`: 読むヘッダー名の一覧
- `queryKeys`: 読むクエリキーの一覧
- `body.mode`: `none` は本文を読みません

## エンドポイントのバインディング

`endpointBindings` に宣言した名前は、`config.endpoints[名前]` で送信先IDとして参照します。テストでは `fixtures/config.json` の値が使われます。Webhook intentの `endpointId` にはこの値を入れます。未設定（`undefined`）の場合を考慮してください。
