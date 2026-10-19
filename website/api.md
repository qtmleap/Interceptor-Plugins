---
title: APIリファレンス
lang: ja
---

# APIリファレンス

## 同期v1の合成プレビュー

フックは同期的に呼ばれ、`{ actions: [...] }` を返します。`actions` は最大2件のWebhook intentです。これらは表示されるだけで、送信されません。実キャプチャへの接続やバックグラウンド実行もありません。型は作成の補助で、入力検証や実行権限の付与ではありません。入力や結果の制限はアプリが実行時に検証します。`read` は宣言として検証・保存されますが、現在の合成入力を絞り込むものではありません。

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

## onRequest {#onrequest}

`onRequest(event, config)` は、合成テストでリクエストのフックを選ぶと呼ばれる同期関数です。manifestにはrequest系のフェーズを宣言しますが、購読からの自動実行は未実装です。`event.request` の任意プロパティは入力に依存するため、存在を確認し、必要な値がなければ `{ actions: [] }` を返します。manifestの `match` は合成テストで適用されないので、フック内にも同じ条件を残します。戻り値は表示専用のWebhook intentで、リクエストの書き換えや転送制御はできません。

<<< ../src/request-summary.ts{ts}

## onResponse {#onresponse}

`onResponse(event, config)` は、合成テストでレスポンスのフックを選ぶと呼ばれる同期関数です。manifestにはresponse系のフェーズを宣言します。`event.response` の任意プロパティも同様に確認し、ステータスやホストなどの条件もフック内で判定します。戻り値は表示専用で、レスポンスは変更されません。

<<< ../src/server-error-filter.ts{ts}

## 読み取り権限（grants）

`read` で必要なものだけを宣言します。

- `metadata`: `method`、`host`、`path`、`status` など
- `headers`: 読むヘッダー名の一覧
- `queryKeys`: 読むクエリキーの一覧
- `body.mode`: `none` は本文を読みません

現在の `read` は検証・保存される宣言です。合成テストでは入力JSONをそのまま渡し、この宣言による絞り込みは行いません。実通信を読み取る許可が付与されたことを意味しません。

## エンドポイントのバインディング

`endpointBindings` に宣言した名前は、`config.endpoints[名前]` で送信先IDとして参照します。テストでは `fixtures/config.json` の値が使われます。Webhook intentの `endpointId` にはこの値を入れます。未設定（`undefined`）の場合を考慮してください。

## HTTP Hook設計 {#http-hooks}

::: info 未実装のAPI
以下は将来のHTTP Hookの設計です。現在の実行環境には `Interceptor.attach` と `rewriteJsonBody` がなく、合成テストに貼り付けても動きません。現在のテンプレートで作成・検証するコードは、上の `onRequest` / `onResponse` を使ってください。
:::

`Interceptor.attach` は、ネイティブのアドレスに対して `onEnter(args)` / `onLeave(retval)` を登録する [FridaのInterceptor](https://frida.re/docs/javascript-api/#interceptor) に着想を得ています。ただし、こちらの対象はネイティブ関数ではなくHTTP通信で、引数や戻り値の形も独自です。

### matchによる絞り込み {#match-gating}

- `hosts` は必須です。`methods` と `path` は省略可能で、省略すると制約なしです。
- 異なるフィールドはAND、同じフィールド内の候補はORで評価されます。
- `path` は `exact` または `prefix` です。
- 条件に合う通信だけがコールバックに届くため、コールバック内で同じ条件を `if` で再確認する必要はありません。
- 現在の合成テストと既存の `onRequest` / `onResponse` ではmanifestの `match` が適用されないため、既存のガードはそのまま残します。
- subscriptionsからの移行、実行順序、件数の上限は未定です。

### Hookの登録 {#hook-registration}

`POST api.example.com/search` に対する登録の完全な例です。`request` と `response` はそれぞれ `onEnter` / `onLeave` を持ちます。

```ts
Interceptor.attach(
  {
    hosts: ["api.example.com"],
    methods: ["POST"],
    path: { kind: "exact", value: "/search" },
  },
  {
    request: {
      onEnter(request) {
        // request.body は説明用にUTF-8へデコードした文字列（オブジェクトの形は未定）
        rewriteJsonBody(request, (json) => {
          json.limit = 5
          json.locale = "ja-JP"
        })
      },
      onLeave(request) {
        // 転送後に呼ばれる。通知APIは未定のため、ここではコメントのみ
      },
    },
    response: {
      onEnter(response) {
        rewriteJsonBody(response, (json) => {
          json.maintenance = true
          json.message = "ただいまメンテナンス中です"
        })
      },
      onLeave(response) {
        // 転送後に呼ばれる。通知APIは未定のため、ここではコメントのみ
      },
    },
  },
)
```

`request` / `response` 引数はトラフィックオブジェクトで、スキーマは未定です。上の `body` は説明用のUTF-8文字列です。1つのプラグインソースに複数の `attach`（例: `POST /search` と `GET /status`）を含められますが、ソース全体を1つのプラグインとして配布し、`id` / `version` もプラグイン全体で1組持ちます。四つのHook全体の実行順序は保証しません。

### request.onEnter {#before-request}

`request.onEnter` はサーバーへ送る前に呼び、リクエストを変更します。次の例では `limit` を変更して `locale` を追加し、それ以外のキーは残します。

```javascript
onEnter(request) {
  rewriteJsonBody(request, (data) => {
    data.limit = 5
    data.locale = "ja-JP"
  })
}
```

変更前:

```json
{
  "keyword": "coffee",
  "limit": 20
}
```

変更後:

```json
{
  "keyword": "coffee",
  "limit": 5,
  "locale": "ja-JP"
}
```

### request.onLeave {#after-request}

`request.onLeave` はサーバーへ送った後に呼びます。引数は送ったリクエストで、レスポンスではありません。送信済みの内容は変更できません。通知の発行方法は未定です。

```javascript
onLeave(request) {
  // 送信したリクエストに応じた後処理を書く
}
```

### response.onEnter {#before-response}

`response.onEnter` はサーバーのレスポンスを受け取り、元のアプリへ返す前に呼び、内容を変更します。`rewriteJsonBody` の前後は次のとおりです（他のキーは保持）。

```javascript
onEnter(response) {
  rewriteJsonBody(response, (data) => {
    data.maintenance = true
    data.message = "ただいまメンテナンス中です"
  })
}
```

変更前:

```json
{
  "maintenance": false,
  "message": "通常営業中",
  "items": []
}
```

変更後:

```json
{
  "maintenance": true,
  "message": "ただいまメンテナンス中です",
  "items": []
}
```

### response.onLeave {#after-response}

`response.onLeave` は元のアプリへ返した後に呼びます。返却したレスポンスをもとに後処理しますが、返却済みの内容は変更できません。通知の発行方法は未定です。

```javascript
onLeave(response) {
  // 返却したレスポンスに応じた後処理を書く
}
```

### rewriteJsonBody {#rewrite-json-body}

`rewriteJsonBody(message, update)` は組み込みのヘルパーです。作者が定義・importすることはなく、`onEnter` でのみ使えます。

- `message` には、その `onEnter` の引数である `request` または `response` を渡します。本文は圧縮を展開し、UTF-8へデコードした `message.body` の文字列を想定しています。
- `update(data)` は解析済みのオブジェクトを同期的に変更します。返り値は無視します。ただしPromiseなどのthenableを返した場合は、成否を待たずエラーとします。
- 変更が成功した後にだけ本文を直列化します。
- 本文が欠落・非文字列・不正なJSON、または解析結果が配列・`null`・数値などの場合は `update` を呼ばず、本文も変更しません。
- `update` の例外、直列化の失敗、thenableの返却では元の本文を保持し、ヘルパーのエラーとして報告します。Hook全体の失敗時の転送やUI表示は未定です。
- `rewriteJsonBody` 自体の返り値は `undefined` で、成功・スキップの状態は返しません。
- 再直列化でJSONの整形（空白など）が変わる場合があり、大きな整数は精度を失う可能性があります。

### 未確定の動作

「送信後」「返却後」の転送完了の定義、部分転送や転送失敗時のHook、例外・時間切れ時の通信処理は未定です。相手の受信・処理を保証するものではありません。本文を変更した後の `Content-Length` の更新や再圧縮はInterceptor側が担う想定ですが、ストリーミング、大きな本文、待ち時間の上限を含めて対応範囲は未確定です。

### 手動実行 {#manual}

手動のショートカット実行は別の将来機能です。五つ目のトラフィックHookではありません。
