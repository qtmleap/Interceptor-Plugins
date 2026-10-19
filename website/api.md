---
title: APIリファレンス
lang: ja
---

# APIリファレンス

## 同期v1の合成プレビュー

フックは同期関数で、`{ actions: [...] }` を返します。`actions` にはWebhookへの送信要求（intent）を最大2件指定できます。送信要求は画面に表示されるだけで、実際には送信されません。キャプチャした通信に合わせた実行や、バックグラウンド実行にも対応していません。型宣言はコードを書くための補助です。入力の検証や実行権限の付与は行いません。アプリは実行時に入力と結果が制限に収まるかを検証します。`read` は宣言として検証・保存されますが、現在の合成テストでは入力の絞り込みには使われません。

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

`onRequest(event, config)` は、合成テストでリクエスト用のフックを選ぶと呼ばれる同期関数です。manifestにはrequest系のフェーズを宣言しますが、購読に基づく自動実行は未実装です。`event.request` に含まれるプロパティは入力によって異なります。必要な値があるかを確認し、なければ `{ actions: [] }` を返します。合成テストではmanifestの `match` で入力を絞り込まないため、サンプルのようにフック内でも条件を判定します。返すのは表示用のWebhookへの送信要求です。リクエストの書き換えや転送制御はできません。

<<< ../src/request-summary.ts{ts}

## onResponse {#onresponse}

`onResponse(event, config)` は、合成テストでレスポンス用のフックを選ぶと呼ばれる同期関数です。manifestにはresponse系のフェーズを宣言します。`event.response` についても必要なプロパティがあるかを確認し、ステータスやホストなどの条件をフック内で判定します。戻り値は表示専用で、レスポンスは変更されません。

<<< ../src/server-error-filter.ts{ts}

## 読み取り権限（grants）

`read` で必要なものだけを宣言します。

- `metadata`: `method`、`host`、`path`、`status` など
- `headers`: 読むヘッダー名の一覧
- `queryKeys`: 読むクエリキーの一覧
- `body.mode`: `none` は本文を読みません

現在の `read` は検証・保存される宣言です。合成テストでは入力JSONをそのまま渡し、この宣言による絞り込みは行いません。実通信を読み取る許可が付与されたことを意味しません。

## エンドポイントのバインディング

`endpointBindings` に宣言した名前に対応する送信先IDは、`config.endpoints[名前]` で参照できます。テストでは `fixtures/config.json` の値を使います。このIDをWebhookへの送信要求の `endpointId` に指定してください。値が設定されていない場合は `undefined` になります。

## HTTP Hook設計 {#http-hooks}

::: info 未実装のAPI
以下は将来のHTTP Hookの設計です。現在の実行環境には `Interceptor.attach` と `rewriteJsonBody` がなく、合成テストに貼り付けても動きません。現在のテンプレートで作成・検証するコードは、上の `onRequest` / `onResponse` を使ってください。
:::

[FridaのInterceptor](https://frida.re/docs/javascript-api/#interceptor) は、ネイティブ関数のアドレスに対して `onEnter(args)` / `onLeave(retval)` を登録します。ここで示す `Interceptor.attach` はその対象とコールバックを組み合わせる形式を参考にしています。対象はHTTP通信で、引数や戻り値の形式もInterceptor Plugin用のものです。

### matchによる絞り込み {#match-gating}

- `hosts` は必須です。`methods` と `path` は省略可能で、省略すると制約なしです。
- 指定したフィールドの条件をすべて満たす必要があります（AND）。同じフィールド内に候補がある場合は、いずれか1つに一致すれば対象です（OR）。
- `path.kind` には、完全一致の `exact` または先頭一致の `prefix` を指定します。
- 条件に合う通信だけがコールバックに届くため、コールバック内で同じ条件を `if` で再確認する必要はありません。
- 現在の合成テストではmanifestの `match` を適用しません。現行の `onRequest` / `onResponse` ではサンプルにある条件判定を残してください。
- subscriptionsからの移行方法、実行順序、登録件数の上限は未定です。

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

各Hookの引数 `request` / `response` はそれぞれリクエストとレスポンスのデータを表すオブジェクトです。具体的な項目や形式は未定で、例中の `body` は説明用のUTF-8文字列としています。たとえば `POST /search` と `GET /status` の処理は同じプラグインソースに `attach` を並べて記述します。ソース全体を1つのプラグインとして配布し、`id` / `version` も全体で1組持ちます。四つのHook全体の実行順序は保証しません。

### request.onEnter {#before-request}

`request.onEnter` は、リクエストをサーバーへ送る前にInterceptorが呼ぶHookです。送信内容を変更する処理をここに書きます。次の例では `limit` を変更して `locale` を追加し、それ以外のキーは残します。

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

`request.onLeave` は、リクエストをサーバーへ送った後にInterceptorが呼ぶHookです。引数は送ったリクエストで、レスポンスではありません。送信済みの内容は変更できません。通知の発行方法は未定です。

```javascript
onLeave(request) {
  // 送信したリクエストに応じた後処理を書く
}
```

### response.onEnter {#before-response}

`response.onEnter` は、サーバーから受け取ったレスポンスを元のアプリへ返す前にInterceptorが呼ぶHookです。返却する内容を変更する処理をここに書きます。次の例は `rewriteJsonBody` で本文の一部を変更し、ほかのキーを残します。

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

`response.onLeave` は、レスポンスを元のアプリへ返した後にInterceptorが呼ぶHookです。返却した内容をもとに後処理を行います。返却済みの内容は変更できません。通知の発行方法は未定です。

```javascript
onLeave(response) {
  // 返却したレスポンスに応じた後処理を書く
}
```

### rewriteJsonBody {#rewrite-json-body}

`rewriteJsonBody(message, update)` は実行環境に組み込む想定の関数です。プラグイン作者が定義やimportをする必要はありません。使える場所は `request.onEnter` と `response.onEnter` だけです。

- `message` には、その `onEnter` の引数である `request` または `response` を渡します。本文は圧縮を展開し、UTF-8へデコードした `message.body` の文字列を想定しています。
- `update(data)` は解析済みのオブジェクトを同期的に変更します。返り値は無視します。ただしPromiseなどのthenableを返した場合は、成否を待たずエラーとします。
- 変更が正常に終わった後にだけ、オブジェクトをJSONの文字列に戻して本文を差し替えます。
- 本文が欠落・非文字列・不正なJSON、または解析結果が配列・`null`・数値などの場合は `update` を呼ばず、本文も変更しません。
- `update` で例外が発生した場合、JSONの文字列に戻せない場合、thenableを返した場合は、元の本文を保ち、ヘルパーのエラーとして報告します。Hook全体が失敗したときの転送やUI表示は未定です。
- `rewriteJsonBody` 自体の返り値は `undefined` で、成功・スキップの状態は返しません。
- JSONを文字列に戻すと、元の空白などの整形は変わる場合があります。また、大きな整数は精度を失う可能性があります。

### 未確定の動作

どの時点を転送完了とみなし、「送信後」「返却後」と判断するかは未定です。部分的な転送や転送失敗の際にどのHookを呼ぶか、例外や時間切れが発生した場合に通信をどう扱うかも決まっていません。相手がデータを受信・処理したことまでは保証しません。本文を変更した後の `Content-Length` の更新や再圧縮はInterceptor側が担う想定です。ストリーミング、大きな本文、待ち時間の上限を含む対応範囲は未確定です。

### 手動実行 {#manual}

ショートカットなどから任意の処理を実行する機能は、4つの通信Hookとは別に検討しています。五つ目の通信Hookではありません。
