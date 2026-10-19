---
title: プラグインを書く
lang: ja
---

<script setup>
import HookFlow from './.vitepress/components/HookFlow.vue'
</script>

# プラグインを書く

`POST https://api.example.com/search`のJSONを変更するプラグインを作ります。対象の通信に対応する場所へファイルを置き、リクエストとレスポンスの転送前に本文を書き換えます。

このガイドで扱うスキーマ2と実通信のHookは開発中です。

## 必要なツール

LinuxとmacOSで同じコマンドを使えます。Bun %%BUN_VERSION%%、Python 3、OpenSSL、Git、Rust、Cコンパイラを用意してください。[開発環境](devcontainer.md)にも含まれています。プラグインの作成・テスト・署名にXcodeは不要です。

## ファイルの構成

1つのプラグインを`plugins/NAME/`にまとめます。`plugin.json`に名前・バージョン・読み書きの権限を、`hooks/`以下に処理を書きます。対象条件やファイルの一覧は`plugin.json`に書きません。

```text
plugins/request-summary/
├── plugin.json
└── hooks/
    └── api.example.com/
        └── search/
            └── POST.ts
```

`hooks/{host}/{path}/{METHOD}.ts`の配置で、対象の通信が決まります。この例では`POST https://api.example.com/search`です。`hooks/api.example.com/GET.ts`なら`GET https://api.example.com/`、`hooks/api.example.com/v1/items/PUT.ts`なら`PUT https://api.example.com/v1/items`を対象にします。

別のAPIにも処理を加えるときは、その対象に対応する場所へファイルを追加します。対象条件とスクリプトの対応は、ビルドがファイルの配置とHookの定義から生成します。

新しいプラグインにはUUIDを一度生成し、`plugin.json`の`id`に記載します。公開後は同じIDを使い続けます。

```sh
python3 -c 'import uuid; print(uuid.uuid4())'
```

<HookFlow locale="ja" />

## JSONを変更する {#jsonを変更する}

`POST.ts`で`Interceptor.attach`にHookを定義します。

```ts
Interceptor.attach({
  request: {
    onEnter(req, cfg) {
      if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) return;
      req.body.limit = 5;
    }
  },
  response: {
    onEnter(res, cfg) {
      if (!res.body || typeof res.body !== 'object' || Array.isArray(res.body)) return;
      res.body.maintenance = true;
    }
  }
});
```

`req`はリクエスト、`res`はレスポンス、`cfg`はプラグインの設定です。この例では`cfg`を使いません。設定が不要なら、第2引数の宣言は省略できます。

この例は、本文がJSONオブジェクトの場合だけ項目を変更します。本文がない場合や配列の場合は、変更しません。対象のホスト・パス・メソッドは、生成されたmanifestを使ってInterceptorが判定します。

読み書きするデータと権限は`plugin.json`で指定します。JSON本文を変更するには、読み取りと対応する書き込み権限の両方が必要です。

<<< ../plugins/request-summary/plugin.json{json}

リクエストが次のJSONなら、`limit`を`50`から`5`に変えてサーバーへ送ります。

```json
{"query":"x","limit":50}
```

```json
{"query":"x","limit":5}
```

サーバーが次のJSONを返したら、`maintenance`を追加してクライアントへ返します。

```json
{"ok":true}
```

```json
{"ok":true,"maintenance":true}
```

`body`はパース済みのJSONです。項目への代入や配列の操作をそのまま書けます。入力JSONの構造は対象APIに合わせて確認してください。転送後の処理は`request.onLeave`と`response.onLeave`に書きます。[4つのHook](api.md#request-onenter)で、それぞれの使い方を説明しています。

## テストを書く

`fixtures/cases.json`に入力と期待する結果を追加します。ここに書いたケースは`bun run check`で実行します。スキーマ2のテストでは`phase`に4つのHook名のいずれかを指定します。

```json
{
  "name": "search limit changed to five on enter",
  "plugin": "request-summary",
  "phase": "request.onEnter",
  "event": {
    "phase": "request.onEnter",
    "request": {
      "method": "POST",
      "host": "api.example.com",
      "path": "/search",
      "body": {"query":"x","limit":50}
    }
  },
  "expected": {
    "actions": [],
    "mutation": {"body":{"query":"x","limit":5}}
  }
}
```

`mutation`は実行環境が作る結果です。作者はHook内で`body`を変更するだけで、`mutation`を組み立てる必要はありません。`expected`の代わりに`expectError: "scriptError"`を指定すると、エラーになることを確認できます。条件に一致しないケースと、転送後に書き換えようとして失敗するケースも確認してください。

## ビルドと検証

```sh
bun install --frozen-lockfile --ignore-scripts
bun run check:authoring
bun run check
bun run build
```

`check:authoring`は型チェック、ツールのテスト、パッケージ生成を検証します。`check`はさらに`fixtures/cases.json`の実行結果、署名、改ざん検出などを検証します。`build`は未署名の開発用パッケージを`build/site/`に生成します。出力先は存在しないか空である必要があります。前回の生成物だけを片付けてから再実行してください。

`build/manifests/NAME.json`にmanifest、`build/scripts/NAME/`にJavaScriptが生成されます。パッケージは`{manifest, sourceFiles}`という構成で、`manifest.matches`に対象条件とHookごとのファイル名、`sourceFiles`に各JSファイルの本文が入ります。生成物は直接編集したりcommitしたりせず、ソースを変更してビルドし直します。公開済みの内容を変えるときは`plugin.json`の`version`を上げます。

## Rustシミュレーター

Rust製の`interceptor-simulator`はアプリと同じQuickJSで構文と実行結果を確認するコマンドです。初回は固定された版のソースを取得し、RustとCコンパイラでビルドします。

```sh
bun run simulator check build/scripts/request-summary/hooks/api.example.com/search/POST.js
bun run simulator run-package build/site/plugins/request-summary.json request.onEnter fixtures/request-event.json fixtures/config.json
```

コマンドに指定した2つの入力ファイルは、このリポジトリに含まれています。`fixtures/request-event.json`は通信データ、`fixtures/config.json`はHookの第2引数に渡す設定です。

<<< ../fixtures/request-event.json{json}

<<< ../fixtures/config.json{json}

自分のAPIを試すときは、これらをコピーして入力を変更します。`fixtures/cases.json`は期待結果まで記載したテストケース集で、`run-package`にそのまま渡すファイルではありません。

`check`は構文だけを検査し、処理は実行しません。`run-package`はパッケージのmanifestから、入力の通信条件とHookに合うファイルを選んで実行します。条件判定・権限・JSONの変更を含む結果を表示し、一致しないファイルは実行しません。転送やWebhook送信は行いません。実際のネットワーク上の順序はアプリ側で確認します。

ビルド後は`.tools/bin/interceptor-simulator`を直接実行できます。同じOS・CPU向けのバイナリなら、実行時にBun、Python、Rust、Xcodeは不要です。Linux版にはビルド先と互換性のあるシステムライブラリが必要です。

## 公開する

パッケージの署名にはEd25519を使います。署名鍵は[公開](publishing.md)のセットアップで登録します。masterへのpush後はCIが署名して配布するため、手元で毎回署名する必要はありません。
