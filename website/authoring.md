---
title: TypeScriptの書き方
lang: ja
---

# TypeScriptの書き方

## ファイルの構成

`src/NAME.ts`、`manifests/NAME.json`、`fixtures/cases.json` を一緒に編集します。ソースとmanifestのファイル名は、拡張子を除いて同じ小文字のkebab-caseにします。リポジトリ／プラグインのIDは初回セットアップ後に変更しません。

## 必要なツール

LinuxとmacOSのどちらでも同じコマンドを使えます。Bun %%BUN_VERSION%%、Python 3、OpenSSL、Git、RustとCコンパイラを用意してください。[開発コンテナ](devcontainer.md)にはこれらのツールが含まれます。

## プラグインを追加する

既存のTypeScriptとmanifestをコピーして、新しい小文字のkebab-case名に変更します。拡張子を除いたファイル名は、両方で統一してください。manifestの `id` には重複しないUUIDを一度生成し、公開後も同じ値を使います。

```sh
python3 -c 'import uuid; print(uuid.uuid4())'
```

`fixtures/cases.json` に各プラグインのテストを最低1件追加します。配列の各要素は次の形式です。

| キー | 内容 |
|---|---|
| `name` | テストの表示名 |
| `plugin` | 拡張子を除いたファイル名（例: `request-summary`） |
| `hook` | `request` または `response` |
| `event` | フックへ渡す入力オブジェクト |
| `expected` | 期待する戻り値のJSON（`actions` を含む） |
| `expectError` | エラーを期待する場合の `"scriptError"` |

`expected` と `expectError` はどちらか片方だけを指定します。[実際のテストデータ](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/fixtures/cases.json)を参考に、動作するケースと何もしないケースを確認してください。

## ビルドとテスト

```sh
bun install --frozen-lockfile --ignore-scripts
bun run check:authoring   # 型チェック、Python/HTTPS、パッケージ生成
bun run check             # QuickJS、署名、改ざん検出まで含めた検証
bun run build             # 未署名の開発用パッケージを build/site/ に生成
```

- TypeScript 5.8.3 は `bun.lock` で固定されています。
- `bun run build` の出力先 `build/site/` は存在しないか空である必要があります。再実行する前に、前回の生成物だけを削除してください。
- `build/scripts/` の生成JavaScriptは編集もcommitもしません。パッケージ生成のたびにTypeScriptから再生成されます。
- 署名鍵はテスト後に公開用ワークフローが用意します。手元で署名する必要はありません。

## バージョンを更新する

ソース、生成されるバイト列、型宣言のいずれかを変えたら、manifestの `version` を上げます。サンプルはv1 manifestのバージョン 1.0.1 です。アプリ側の新しいスキーマは不要です。

## フックを書く

manifestに宣言した購読に対応するよう、トップレベルに `onRequest` または `onResponse` という関数を定義します。各プラグインは別々にコンパイルされるため、ファイル間で関数名が重複しても構いません。

<<< ../src/request-summary.ts{ts}

このサンプルでは、テスト用の `preview` バインディングと入力を使います。新しいフックを書くときは、バインディングや省略可能な入力項目を確認し、必要な値がなければ `{ actions: [] }` を返してください。

型は [APIリファレンス](api.md) を参照してください。



## シミュレーター

先に `bun run check` を実行すると、例で使う `build/scripts/request-summary.js` が生成されます。入力ファイルの内容は[APIのテスト入力](api.md#テスト入力)を参照してください。

Rust製の `interceptor-simulator` は、アプリと同じQuickJSでJavaScriptを検査・実行するコマンドです。初回はバージョンを固定したQuickJSのソースを取得し、RustとCコンパイラでビルドします。

```sh
bun run simulator check build/scripts/request-summary.js
bun run simulator run build/scripts/request-summary.js onRequest fixtures/request-event.json fixtures/config.json
```

`check` は構文だけを検査し、スクリプトを実行しません。構文が正しくても、フックが存在しないことや戻り値の不正は検出できません。入力JSONを使う `run` と、期待値まで比較する `bun run check` も実行してください。`run` が返すアクションはJSONとして表示され、Webhookは送信されません。

ビルド後は `.tools/bin/interceptor-simulator` を直接実行できます。同じOS・CPU向けのバイナリなら、実行時にBun、Python、Rust、Xcodeは不要です。Linux版にはビルド先と互換性のあるシステムライブラリが必要です。

## 実行環境の制約

実行環境では、1つのグローバルスクリプトを評価してフックを同期的に呼び出します。import/export、非同期コード、Promise、TypedArray、Node／ブラウザAPIは使えません。`fetch`、console、ファイルシステム、タイマー、モジュールローダーもありません。コンパイラはこれらの一般的な構文を拒否しますが、セキュリティサンドボックスではありません。スクリプトはアプリ内の制限付きQuickJS環境で実行されます。

プレビューが返すWebhookへの送信要求（intent）は最大2件です。実際の送信や、キャプチャした通信に合わせた自動実行は行いません。SHA-256は生成されたパッケージのバイト列から計算し、署名付きの一覧がそのハッシュを認証します。

公開は[公開](publishing.md)、Linuxでの開発は[開発コンテナ](devcontainer.md)を参照してください。
