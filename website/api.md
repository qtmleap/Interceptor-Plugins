---
title: APIリファレンス
lang: ja
---

# APIリファレンス

## Interceptor.attach

`Interceptor.attach(match, hooks)`で、対象の通信と、その通信で呼ぶHookを指定します。ホスト、パス、メソッドなどの条件が一致したときだけ、対応する関数が呼ばれます。1つのソースに対象と処理を並べて、1つのプラグインとして配布できます。

```ts
const search: Interceptor.Match = {
  hosts: ['api.example.com'],
  methods: ['POST'],
  path: { kind: 'exact', value: '/search' }
};

Interceptor.attach(search, {
  request: {
    onEnter(request) {
      if (!request.body || typeof request.body !== 'object' || Array.isArray(request.body)) return;
      request.body.limit = 5;
    },
    onLeave(request, config) {
      const endpointId = config.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook',
        endpointId,
        json: { path: request.path! }
      }] };
    }
  },
  response: {
    onEnter(response) {
      if (!response.body || typeof response.body !== 'object' || Array.isArray(response.body)) return;
      response.body.maintenance = true;
    },
    onLeave(response, config) {
      const endpointId = config.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook',
        endpointId,
        json: { status: response.status! }
      }] };
    }
  }
});
```

必要なHookだけを定義できます。第1引数は、そのHookが処理するリクエストまたはレスポンスです。第2引数の`config`には設定値とエンドポイントのバインディングが入ります。`response.request`から、そのレスポンスに対応するリクエストを参照できます。

### 対象条件

`match`はmanifestの`matches`に記載した条件のいずれかと同じ内容にします。宣言にない対象をソースで指定すると、実行時に拒否されます。

- `hosts`: 完全一致するホスト名の配列。ワイルドカードや正規表現は使えません。
- `methods`: 対象のHTTPメソッドの配列。省略するとメソッドで絞り込みません。
- `path`: `exact`で完全一致、`prefix`で前方一致。クエリ文字列を除いたパスに適用します。
- `status`: レスポンスのステータス範囲。`min`と`max`の両端を含みます。リクエストのHookには指定しません。

項目を組み合わせた場合は、すべての条件を満たす通信が対象です。配列内の値はいずれかに一致すれば対象になります。たとえば、対象をステータス500〜599に絞るだけなら、`read.metadata`に`status`を含める必要はありません。Hook内で`response.status`を読む場合に、その項目の権限が必要です。

## request.onEnter {#request-onenter}

リクエストをサーバーへ転送する前に呼びます。`read.body.mode`が`json`で、`write.requestBody`が`true`なら、`request.body`のJSONを変更できます。

```ts
Interceptor.attach(search, {
  request: {
    onEnter(request) {
      if (!request.body || typeof request.body !== 'object' || Array.isArray(request.body)) return;
      request.body.limit = 5;
    }
  }
});
```

本文全体を置き換える場合は`request.body = { query: 'example', limit: 5 }`のように代入します。変更がなければ元の本文をそのまま転送します。専用の書き換え関数を用意する必要はありません。

## request.onLeave {#request-onleave}

リクエストの転送が成功した後に呼びます。送信前のHookで変更した場合は、変更後の内容が渡ります。サーバーが受信・処理したことまでは保証しません。転送に失敗した場合は呼びません。

```ts
Interceptor.attach(search, {
  request: {
    onLeave(request, config) {
      const endpointId = config.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook',
        endpointId,
        json: { method: request.method!, path: request.path! }
      }] };
    }
  }
});
```

入力は読み取り専用です。このHookで本文を変更しようとするとエラーになります。返したアクションは合成テストの結果欄に表示します。実通信では戻り値を保存・送信しません。`type: 'webhook'`という形式を使いますが、外部へのHTTP送信は行いません。

## response.onEnter {#response-onenter}

サーバーのレスポンスをクライアントへ転送する前に呼びます。`read.body.mode`が`json`で、`write.responseBody`が`true`なら、`response.body`のJSONを変更できます。

```ts
Interceptor.attach(search, {
  response: {
    onEnter(response) {
      if (!response.body || typeof response.body !== 'object' || Array.isArray(response.body)) return;
      response.body.maintenance = true;
    }
  }
});
```

`response.request`は参照用です。ここからリクエストを変更することはできません。

## response.onLeave {#response-onleave}

レスポンスの転送が成功した後に呼びます。クライアントへ返した内容を使って結果を作るときに使います。クライアント側での受信・処理の完了までは保証しません。転送に失敗した場合は呼びません。

```ts
Interceptor.attach(search, {
  response: {
    onLeave(response, config) {
      const endpointId = config.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook',
        endpointId,
        json: { path: response.request.path!, status: response.status! }
      }] };
    }
  }
});
```

入力は読み取り専用です。戻り値は合成テストの結果欄で確認できます。実通信では保存・送信されません。

## manifestと権限

新しいプラグインは`schemaVersion: 2`を使います。次のmanifestは[サンプル](examples.md#request-summary)と同じものです。

<<< ../manifests/request-summary.json{json}

`id`は公開後も維持するプラグインのUUID、`version`は変更時に上げるバージョンです。`matches`は1〜16件、ソース内の`attach`は最大16回です。`read`には、処理に必要な情報だけを指定します。

- `metadata`: `method`、`host`、`path`、`status`などの項目
- `headers`: 読み取るヘッダー名
- `queryKeys`: 読み取るクエリキー
- `body.mode`: `none`は本文を渡さず、`json`はJSON本文を渡す

`write.requestBody`と`write.responseBody`は対応する`onEnter`でJSONを変更する権限です。メソッド、URL、ヘッダー、ステータスは変更できません。権限のない値を読み取る前提でコードを書かないでください。

`endpointBindings`は、合成テストでWebhook形式のアクションを作るときに使う名前の配列です。使わない場合も`[]`を記載します。テストでは`config.endpoints.preview`などにテスト用IDを指定します。実通信ではエンドポイントIDを渡さないため、例ではIDがない場合にアクションを返さず終了します。ホストやメソッドの確認は対象条件で行います。`settings`は`config.settings`で参照します。

旧スキーマ1の`onRequest`と`onResponse`は既存パッケージの合成テスト用に残っています。4つのHookを使うソースでは定義しません。スキーマ1のパッケージは実通信では有効にできません。

## 実行条件と制限

各Hookのたびに新しい実行環境でソースを読み込みます。関数の外の変数を使って、`onEnter`から`onLeave`へ状態を引き継ぐことはできません。

実通信でJSON本文を処理する対象は、UTF-8の`application/json`または`+json`で、圧縮されていない24 KiB以下の本文です。圧縮データ、大きな本文、SSE、WebSocketなどへのUpgrade、`Expect: 100-continue`、HEADや本文を持たないレスポンスは本文のHook処理を通さず転送します。接続内の保留データにも64 KiBの上限があります。

スクリプトの例外や時間制限超過では元の通信内容を転送します。利用者が承認を取り消した場合は接続を終了します。実行は同期式で、`fetch`、Promise、タイマー、ファイル操作、NodeやブラウザのAPIは使えません。

1回の実行は50 ms、ヒープ8 MiB、ソース128 KiB、入力64 KiB、設定8 KiB、結果32 KiBまでです。返せるアクションは最大2件です。

## 型宣言

型宣言は作成時の補助です。入力と権限の検証は実行時にも行います。

<<< ../types/interceptor.d.ts{ts}
