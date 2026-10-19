---
title: APIリファレンス
lang: ja
---

# APIリファレンス

## 同期v1の合成プレビュー

フックは同期的に実行される関数で、`{ actions: [...] }` を返します。`actions` にはWebhookへの送信要求（intent）を最大2件指定できます。送信要求は画面に表示されるだけで、実際には送信されません。キャプチャした通信に合わせた実行や、バックグラウンド実行にも対応していません。型宣言はコードを書く際の補助です。型宣言そのものが入力を検証したり、実行権限を付与したりすることはありません。アプリは実行時に、入力と結果が制限の範囲内かを検証します。`read` は宣言として検証・保存されますが、現在の合成テストでは入力の絞り込みには使われません。

## 型宣言

<<< ../types/interceptor.d.ts{ts}

## テスト入力

`event` は通信データ、`config` はプラグインへ渡す設定です。シミュレーターの例では次のJSONファイルを使います。

`fixtures/request-event.json`:

<<< ../fixtures/request-event.json{json}

`fixtures/config.json`:

<<< ../fixtures/config.json{json}

`run` コマンドで `onRequest` を指定すると、その関数に2つのJSONオブジェクトを渡します。`phase` は入力JSONに書かれた値です。合成テストではフックの選択と入力JSONをそれぞれ指定します。`phase` に応じて入力項目を追加したり、manifestの条件で削ったりする処理はありません。`event.request` や `event.response` も入力に含めた内容がそのまま渡されます。

`preview` は、このサンプルが使うバインディング名です。`config.endpoints.preview` のテスト用IDを、戻り値の `endpointId` に指定します。合成テストでは実際の送信先を登録する必要はありません。アプリではスクリプト詳細のテスト欄で、フック、入力JSON、設定JSONを編集できます。

## manifestのフィールド

manifestの具体例は [サンプル](examples.md) にあります。

| フィールド | 内容 |
|---|---|
| `schemaVersion` | 常に `1` |
| `id` | プラグインのUUID。公開後は変えません |
| `name` / `version` | 表示名と、変更ごとに上げるバージョン |
| `subscriptions` | `phase`（`request.headers`・`request.completed`・`response.headers`・`response.completed`）と `match` |
| `read` | フックが読める情報の権限（grants） |
| `endpointBindings` | Webhook送信先の名前 |
| `settings` | 設定値（サンプルでは空） |

`match` には `hosts`、`methods`、`path`、`status` を指定できます。`path` は `{ "kind": "exact", "value": "/api/items" }` または `{ "kind": "prefix", "value": "/api/" }`、`status` は `min`/`max` の範囲です。合成テストでは `match` が適用されないため、フック内でも同じ条件を判定してください。

## onRequest {#onrequest}

`onRequest(event, config)` は、合成テストでリクエスト用のフックを選ぶと呼ばれる同期関数です。manifestにはrequest系のフェーズを宣言しますが、購読に基づく自動実行は未実装です。`event.request` に含まれるプロパティは入力によって異なります。必要な値が含まれているかを確認し、なければ `{ actions: [] }` を返します。合成テストではmanifestの `match` で入力を絞り込まないため、サンプルのようにフック内でも条件を判定します。戻り値は画面に表示するためのWebhook送信要求です。リクエストの書き換えや転送制御はできません。

<<< ../src/request-summary.ts{ts}

## onResponse {#onresponse}

`onResponse(event, config)` は、合成テストでレスポンス用のフックを選ぶと呼ばれる同期関数です。manifestにはresponse系のフェーズを宣言します。`event.response` についても必要なプロパティがあるかを確認し、ステータスやホストなどの条件をフック内で判定します。戻り値は表示のみに使用され、レスポンスは変更されません。

<<< ../src/server-error-filter.ts{ts}

## 読み取り権限（grants）

`read` で必要なものだけを宣言します。

- `metadata`: `method`、`host`、`path`、`status` など
- `headers`: 読むヘッダー名の一覧
- `queryKeys`: 読むクエリキーの一覧
- `body.mode`: `none` は本文を読みません

現在の `read` は検証・保存の対象となる宣言です。合成テストでは入力JSONをそのまま渡し、この宣言による絞り込みは行いません。実通信を読み取る許可が付与されたことを意味しません。

## エンドポイントのバインディング

`endpointBindings` に宣言した名前に対応する送信先IDは、`config.endpoints[名前]` で参照できます。テストでは `fixtures/config.json` の値を使います。Webhookへの送信要求にはこのIDを `endpointId` として指定してください。値が設定されていない場合は `undefined` になります。
