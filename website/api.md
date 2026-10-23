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

`Interceptor.attach(hooks)`で、このファイルの処理を登録します。ビルドはファイルの配置場所からホスト・パス・メソッドを読み取り、`request`・`response`内のHook定義とともにmanifestへ書き出します。`attach`には対象条件やプラグインIDは渡しません。

`actions`はHookが返す従来のWebhook形式のアクションの配列です。`type: 'webhook'`は通知先の識別子`endpointId`とJSONデータを含む形式名です。`endpointId`には送信先URLではなく、`cfg.endpoints`から取得するIDを使います。合成テストではアクションの内容を結果欄で確認でき、HTTP送信は行いません。実通信ではこのWebhook形式の戻り値を保存・送信しません。別APIへのGET送信には[Interceptor.send](#interceptor-send)を使います。

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

リクエストの転送が成功した後に、サーバーへ転送した内容を読み取るHookです。入力は読み取り専用で、送信前のHookで変更した場合は変更後の内容が渡ります。サーバーが受信・処理したことまでは保証しません。転送に失敗した場合は呼びません。

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

このHookで本文を変更しようとするとエラーになります。合成テストでは渡された通信データからアクションを返し、結果欄で内容を確認できます。実通信では戻り値のWebhook形式のアクションを保存・送信しません。

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

レスポンスの転送が成功した後に、クライアントへ転送した内容を読み取るHookです。入力は読み取り専用です。クライアント側での受信・処理の完了までは保証しません。転送に失敗した場合は呼びません。

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

このHookで本文を変更しようとするとエラーになります。合成テストでは渡された通信データからアクションを返し、結果欄で内容を確認できます。実通信では戻り値のWebhook形式のアクションを保存・送信しません。

## fetch {#fetch}

`response.onLeave`から標準の`fetch`を呼び、応答を`await`できます。
URL・メソッド・ヘッダー・本文はJS内に記述します。送信先をmanifestの`outbound`へ重ねて宣言する必要はありません。

```ts
Interceptor.attach({
  response: {
    async onLeave(res) {
      const response = await fetch('https://api.example.com/results', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ result: res.body })
      });
      if (!response.ok) throw new Error('request failed');
      const result = await response.json();
    }
  }
});
```

この実装はHTTPSの公開ホスト・443番ポートへのGET/POST/PUTとJSON本文に対応します。
クエリ文字列、リダイレクト、ストリーミング、圧縮応答、自動Cookieは扱いません。
応答の`status`・`ok`・`bodyUsed`を確認し、`text()`または`json()`で本文を1回だけ読み取れます。
`fetch`を使うHookは、元の転送を待たせず後続実行します。既存の同期Hookは従来どおりです。
非同期の補助関数は`response.onLeave`内に置きます。

本文は8KiB、応答は1MiB、1回のHookは64リクエスト・累計16MiBまでです。
処理時間と並列数にも上限があり、承認の取り消しやトンネル終了でキャンセルします。
既存の合成テスト画面はネットワークを実行しません。オフラインの応答を使う検証には
`interceptor-simulator run-package-fetch`を使います。

## Interceptor.send {#interceptor-send}

`Interceptor.send(binding, { headers })`は、manifestの`outbound`に宣言した別のAPIへGETリクエストを送るための関数です。送信要求を登録してすぐに戻り、`void`を返します。実際のHTTP送信はHookの検証後にアプリが行います。Hookから送信結果は参照できず、元の通信も送信完了を待ちません。`fetch`、Promise、`Response`のAPIではありません。

```ts
Interceptor.send('bearer', { headers: { authorization: 'Bearer ' + token } });
```

第2引数と、その中の`headers`は必須です。ヘッダーが不要なら`{ headers: {} }`を渡します。`SendOptions`に指定できるのは、文字列の値を持つ`headers`だけです。ヘッダー名は宣言の`headers`に含めます。URLと`GET`メソッドは宣言で固定し、本文は送れません。`url`、`method`、`body`、文字列以外のヘッダー値はエラーになります。

既存の4つのHookで、対象の通信がJSON本文などの実行条件を満たしている場合に呼べます。元の通信のメソッドを`GET`に限定するものではありません。ファイルのトップレベルでは`attach`を1回呼び、登録した`onEnter`または`onLeave`の関数内で`send`を直接呼びます。`send`を別の変数に代入して呼ぶ書き方や、`Interceptor['send']`は使えません。`attach`でHookを登録している間も`send`は呼べません。

### outboundの宣言 {#outbound-metadata}

`plugin.json`に、名前付きのリクエストを最大4件宣言します。各項目は`url`、`method`（`"GET"`）、`headers`（小文字の名前を最大8件）だけです。

```json
"outbound": {
  "bearer": {
    "url": "https://interceptor-traffic-fixture.lemonandchan.workers.dev/auth/bearer",
    "method": "GET",
    "headers": ["authorization"]
  }
}
```

- URLは小文字の`https://`で始まる2048バイト以下のASCII文字列にします。小文字のDNSホストと`/`から始まるパスが必要です。ポート番号は`:443`も含めて省略し、userinfo・クエリ・フラグメントは指定しません。ホストには2つ以上のラベルが必要で、末尾のラベルに英字を含めます。IPアドレス、単一ラベルのホスト、`.local`・`.localhost`で終わるホストは使えません。
- パスは1024バイト以下です。そのまま書けるのは英数字、`-._~`、`!$&'()*+,;=`、`:`、`@`、`/`だけで、それ以外はパーセントエンコードします。エンコードされたUTF-8バイトは使えますが、制御文字・DEL・バックスラッシュにデコードされるエスケープは使えません。
- 送信先は宣言したURLに固定されます。パターン、リダイレクト、URLの置き換えは使えません。`host`などの通信制御ヘッダー、`proxy-*`、`set-cookie`は宣言できません。
- manifestはビルドが生成します。`plugin.json`が編集元で、`outbound`はそのままmanifestへ書き出されます。生成されたmanifestは手で編集しないでください。
- `outbound`を追加・変更すると、利用者が承認する送信先が変わります。固定された送信先が承認画面に表示され、更新時は再承認が必要です。
- 1回のHook実行で記録できるアクションは、従来のアクションと合わせて2件までです。同じ通信の同じHookタイミング（例えば`response.onLeave`）で行うGET送信は、全プラグインを合わせて2件までです。合計が2件を超えた場合や、送信前のいずれかの検証に失敗した場合は、そのタイミングに登録した送信要求をすべて破棄します。不明な送信先や許可されていないヘッダーによる検証エラーは、例外を捕捉しても取り消せません。実際のHTTP送信で起きる通信エラーは送信前の検証エラーとは別で、元の通信には影響しません。
- `Set-Cookie`から最初のCookieのペア（`name=value`）を取り出して`cookie`に渡し、`Path`などの属性は含めません。Cookieの自動送信や保存はしません。合成テストとRustシミュレータは記録したアクションを表示するだけで、HTTP送信は行いません。

トークンとCookieの流れは[サンプル](examples.md#outbound-example)を参照してください。

## manifestと権限

`plugin.json`にはプラグインの名前・バージョン・権限などを記載します。このガイドのスキーマ2は開発中です。次の設定は[サンプル](examples.md#request-summary)と同じものです。対象条件やJSファイルとの対応は記載しません。

<<< ../plugins/request-summary/plugin.json{json}

`id`は公開後も維持するプラグインのUUID、`version`は変更時に上げるバージョンです。1つのプラグインに最大16個のHookファイルを置けます。各ファイルは`hooks/`以下のフォルダー構成とファイル名で、対象のホスト・パス・メソッドを指定します。各ファイルではトップレベルで`attach`を1回呼び、必要なHookを定義します。`read`には、処理に必要な情報だけを指定します。

- `metadata`: `method`、`host`、`path`、`status`などの項目
- `headers`: 読み取るヘッダー名
- `queryKeys`: 読み取るクエリキー
- `body.mode`: `none`は本文を渡さず、`json`はJSON本文を渡す

`write.requestBody`と`write.responseBody`は対応する`onEnter`でJSONを変更する権限です。メソッド、URL、ヘッダー、ステータスは変更できません。権限のない値を読み取る前提でコードを書かないでください。

`endpointBindings`は、合成テストでWebhook形式のアクションを作るときに使う名前の配列です。使わない場合も`[]`を記載します。テストでは`cfg.endpoints.preview`などにテスト用IDを指定します。実通信ではエンドポイントIDを渡さないため、例ではIDがない場合にアクションを返さず終了します。ホストやメソッドの確認は対象条件で行います。`settings`は`cfg.settings`で参照します。

ビルドが作るパッケージは`{manifest, sourceFiles}`です。`manifest.matches`にはホスト・メソッド・完全一致のパスと、`hooks.request.onEnter`などのファイル参照が入ります。`sourceFiles`はファイル名とJS本文の対応表です。これらはビルドが生成するため、`plugin.json`に`matches`・`hooks`・`sourceFiles`を手書きするとエラーになります。

## 実行条件と制限

各Hookの実行前にmanifestで通信条件とHookを判定し、一致するファイルを新しい実行環境へ読み込みます。一致しないファイルは実行しません。関数の外の変数を使って、`onEnter`から`onLeave`へ状態を引き継ぐことはできません。

実通信でJSON本文を処理する対象は、UTF-8の`application/json`または`+json`で、圧縮されていない24 KiB以下の本文です。圧縮データ、大きな本文、SSE、`Expect: 100-continue`、HEADや本文を持たないレスポンスは本文のHook処理を通さず転送します。接続内で保持する本文、待機中のデータ、書き込み完了を待つデータ、`onLeave`が保持する本文の合計は64 KiBまでです。

復号後の接続内でUpgradeや再度のCONNECTを受けた場合は、先行するレスポンスの後に`501`を返して接続を終了します。要求していない`101`レスポンスを受けた場合も接続を終了します。

アプリの共通プロセッサーはHookを1つずつ実行し、待機は最大8件です。上限を超えた`onEnter`は元の通信内容を転送します。処理が完了していない`onLeave`の通知は接続ごとに最大4件です。超過分は転送を止めずに省略します。通知の実行は保証されません。

スクリプトの例外や時間制限超過では元の通信内容を転送します。通信の取得への同意やプラグインの承認を利用者が取り消した場合は接続を終了します。`response.onLeave`の`fetch`だけは非同期に実行できます。それ以外のHookは同期式です。タイマー、ファイル操作、Nodeやその他のブラウザAPIは使えません。

1回の実行は50 ms、ヒープ8 MiB、プラグイン内のソース合計128 KiB、入力64 KiB、設定8 KiB、結果32 KiBまでです。返せるアクションは最大2件です。

## 型宣言

型宣言は作成時の補助です。入力と権限の検証は実行時にも行います。

<<< ../types/interceptor.d.ts{ts}
