---
title: APIリファレンス
lang: ja
---

<script setup>
import HookFlow from './.vitepress/components/HookFlow.vue'
</script>

# APIリファレンス

<HookFlow locale="ja" />

## Interceptor.attach

`Interceptor.attach(hooks)`で、このファイルの処理を登録します。ビルドはファイルの配置場所からホスト・パス・メソッドを読み取り、`request`・`response`内のHook定義とともにmanifestへ書き出します。JavaScriptから対象条件やIDは渡しません。

次のコードを`hooks/api.example.com/search/POST.ts`に置くと、`POST https://api.example.com/search`の処理になります。Interceptorは生成されたmanifestで通信条件とHookを判定し、対応するJSファイルをロードして実行します。

```ts
Interceptor.attach({
  request: {
    onEnter(req, cfg) {
      if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) return;
      req.body.limit = 5;
    },
    onLeave(req, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook',
        endpointId,
        json: { path: req.path! }
      }] };
    }
  },
  response: {
    onEnter(res, cfg) {
      if (!res.body || typeof res.body !== 'object' || Array.isArray(res.body)) return;
      res.body.maintenance = true;
    },
    onLeave(res, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook',
        endpointId,
        json: { status: res.status! }
      }] };
    }
  }
});
```

必要なHookだけを定義できます。リクエストでは`(req, cfg)`、レスポンスでは`(res, cfg)`を受け取ります。`req`と`res`は通信データ、`cfg`はプラグインの設定です。manifestの`settings`は`cfg.settings`で参照できます。合成テスト用のエンドポイントIDは`cfg.endpoints`から参照します。

設定を使わない場合は、第2引数の宣言を省略して`onEnter(res) { ... }`とも書けます。`res.request`から、そのレスポンスに対応するリクエストを参照できます。

### ファイルと対象条件 {#対象条件}

ビルドが対象条件とファイル参照を生成します。開発者は`hooks/{host}/{path}/{METHOD}.ts`へ処理を書きます。ルートの`/`は`hooks/{host}/{METHOD}.ts`、例えば`hooks/api.example.com/GET.ts`です。

ホスト名は小文字、HTTPメソッドは大文字で指定します。パスは大文字と小文字を区別する完全一致です。クエリ文字列は判定に含めません。動的パス、ワイルドカード、末尾スラッシュ付きのパス、非ASCII文字や`%`を含むパスは、このディレクトリ構成では指定できません。それらを別のパスへ読み替えることもありません。

同じプラグインに別の対象を加える場合は、その対象の場所にファイルを追加します。手順は[プラグインを書く](authoring.md)を参照してください。

## request.onEnter {#request-onenter}

リクエストをサーバーへ転送する前に呼びます。`read.body.mode`が`json`で、`write.requestBody`が`true`なら、`req.body`のJSONを変更できます。

```ts
Interceptor.attach({
  request: {
    onEnter(req, cfg) {
      if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) return;
      req.body.limit = 5;
    }
  }
});
```

本文全体を置き換える場合は`req.body = { query: 'example', limit: 5 }`のように代入します。変更がなければ元の本文をそのまま転送します。専用の書き換え関数を用意する必要はありません。

## request.onLeave {#request-onleave}

リクエストの転送が成功した後に呼びます。送信前のHookで変更した場合は、変更後の内容が渡ります。サーバーが受信・処理したことまでは保証しません。転送に失敗した場合は呼びません。

```ts
Interceptor.attach({
  request: {
    onLeave(req, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook',
        endpointId,
        json: { method: req.method!, path: req.path! }
      }] };
    }
  }
});
```

入力は読み取り専用です。このHookで本文を変更しようとするとエラーになります。返したアクションは合成テストの結果欄に表示します。実通信では戻り値を保存・送信しません。`type: 'webhook'`という形式を使いますが、外部へのHTTP送信は行いません。

## response.onEnter {#response-onenter}

サーバーのレスポンスをクライアントへ転送する前に呼びます。`read.body.mode`が`json`で、`write.responseBody`が`true`なら、`res.body`のJSONを変更できます。

```ts
Interceptor.attach({
  response: {
    onEnter(res, cfg) {
      if (!res.body || typeof res.body !== 'object' || Array.isArray(res.body)) return;
      res.body.maintenance = true;
    }
  }
});
```

`res.request`は参照用です。ここからリクエストを変更することはできません。

## response.onLeave {#response-onleave}

レスポンスの転送が成功した後に呼びます。クライアントへ返した内容を使って結果を作るときに使います。クライアント側での受信・処理の完了までは保証しません。転送に失敗した場合は呼びません。

```ts
Interceptor.attach({
  response: {
    onLeave(res, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{
        type: 'webhook',
        endpointId,
        json: { path: res.request.path!, status: res.status! }
      }] };
    }
  }
});
```

入力は読み取り専用です。戻り値は合成テストの結果欄で確認できます。実通信では保存・送信されません。

## manifestと権限

`plugin.json`にはプラグインの名前・バージョン・権限などを記載します。このガイドのスキーマ2は開発中です。次の設定は[サンプル](examples.md#request-summary)と同じものです。対象条件やJSファイルとの対応は記載しません。

<<< ../plugins/request-summary/plugin.json{json}

`id`は公開後も維持するプラグインのUUID、`version`は変更時に上げるバージョンです。1つのプラグインに最大16個のルートファイルを置けます。各ファイルではトップレベルで`attach`を1回呼び、必要なHookを定義します。`read`には、処理に必要な情報だけを指定します。

- `metadata`: `method`、`host`、`path`、`status`などの項目
- `headers`: 読み取るヘッダー名
- `queryKeys`: 読み取るクエリキー
- `body.mode`: `none`は本文を渡さず、`json`はJSON本文を渡す

`write.requestBody`と`write.responseBody`は対応する`onEnter`でJSONを変更する権限です。メソッド、URL、ヘッダー、ステータスは変更できません。権限のない値を読み取る前提でコードを書かないでください。

`endpointBindings`は、合成テストでWebhook形式のアクションを作るときに使う名前の配列です。使わない場合も`[]`を記載します。テストでは`cfg.endpoints.preview`などにテスト用IDを指定します。実通信ではエンドポイントIDを渡さないため、例ではIDがない場合にアクションを返さず終了します。ホストやメソッドの確認は対象条件で行います。`settings`は`cfg.settings`で参照します。

ビルドが作るパッケージは`{manifest, sourceFiles}`です。`manifest.matches`にはホスト・メソッド・完全一致のパスと、`hooks.request.onEnter`などのファイル参照が入ります。`sourceFiles`はファイル名とJS本文の対応表です。これらはビルドが生成するため、`plugin.json`に`matches`・`hooks`・`sourceFiles`を手書きするとエラーになります。

## 実行条件と制限

各Hookの実行前にmanifestで通信条件とHookを判定し、一致するファイルを新しい実行環境へ読み込みます。一致しないファイルは実行しません。関数の外の変数を使って、`onEnter`から`onLeave`へ状態を引き継ぐことはできません。

実通信でJSON本文を処理する対象は、UTF-8の`application/json`または`+json`で、圧縮されていない24 KiB以下の本文です。圧縮データ、大きな本文、SSE、WebSocketなどへのUpgrade、`Expect: 100-continue`、HEADや本文を持たないレスポンスは本文のHook処理を通さず転送します。接続内の保留データにも64 KiBの上限があります。

スクリプトの例外や時間制限超過では元の通信内容を転送します。利用者が承認を取り消した場合は接続を終了します。実行は同期式で、`fetch`、Promise、タイマー、ファイル操作、NodeやブラウザのAPIは使えません。

1回の実行は50 ms、ヒープ8 MiB、プラグイン内のソース合計128 KiB、入力64 KiB、設定8 KiB、結果32 KiBまでです。返せるアクションは最大2件です。

## 型宣言

型宣言は作成時の補助です。入力と権限の検証は実行時にも行います。

<<< ../types/interceptor.d.ts{ts}
