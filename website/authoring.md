---
title: TypeScriptの書き方
lang: ja
---

# TypeScriptの書き方

## ファイルの構成

`src/NAME.ts`、`manifests/NAME.json`、`fixtures/cases.json` を一緒に編集します。ソースとmanifestには、拡張子を除いて同じ小文字のkebab-case名を付けます。リポジトリ／プラグインのIDは初回セットアップ後に変更しません。

## 必要なツール

Bun %%BUN_VERSION%%、Python 3、OpenSSL、Gitを使います。すべての検証を行う `bun run check` には、Xcode 27 / Swift 6.4を選択したMacが必要です。Linuxでは `check:authoring` を実行できます。

## プラグインを追加する

既存のTypeScriptとmanifestをコピーし、新しい小文字のkebab-case名に変更します。拡張子を除いた名前は両方で揃えてください。manifestの `id` には重複しないUUIDを一度生成し、公開後も同じ値を使います。

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
bun run check:authoring   # Linuxでも可: 型チェック、Python/HTTPS、決定的なパッケージ
bun run check             # Mac: 実QuickJS、署名、テンプレート全体の検証
bun run build             # 未署名の開発用パッケージを build/site/ に生成
```

- TypeScript 5.8.3 は `bun.lock` で固定されています。
- `bun run build` の出力先 `build/site/` は存在しないか空である必要があります。再実行する前に、前回の生成物だけを削除してください。
- `build/scripts/` の生成JavaScriptは編集もcommitもしません。パッケージ生成のたびにTypeScriptから再生成されます。
- 署名鍵はテスト後に公開用ワークフローが用意します。手元で署名する必要はありません。

## バージョンを更新する

ソース、生成されるバイト列、型宣言のいずれかを変えたら、manifestの `version` を上げます。サンプルはv1 manifestのバージョン 1.0.1 です。アプリ側の新しいスキーマは不要です。

## フックを書く

manifestに宣言した購読に合わせ、トップレベルに `onRequest` または `onResponse` という関数を定義します。各プラグインは別々にコンパイルされるため、ファイル間で関数名が重複しても構いません。

<<< ../src/request-summary.ts{ts}

このサンプルはテスト用の `preview` バインディングと入力を使います。新しいフックを書くときは、バインディングや省略可能な入力項目の有無を確認し、必要な値がなければ `{ actions: [] }` を返してください。

型は [APIリファレンス](api.md) を参照してください。

::: warning 将来の設計
`Interceptor.attach` / `rewriteJsonBody` は[HTTP Hook設計](api.md#http-hooks)と[将来の例](examples.md#future-http-hooks)にありますが未実装です。現在はコンパイル、テスト、公開できません。
:::

## 実行環境の制約

実行環境は1つのグローバルスクリプトを評価し、フックを同期的に呼びます。import/export、非同期コード、Promise、TypedArray、Node／ブラウザAPIは使えません。`fetch`、console、ファイルシステム、タイマー、モジュールローダーもありません。コンパイラはこれらの一般的な構文を拒否しますが、セキュリティサンドボックスではありません。スクリプトはアプリ内の制限付きQuickJS環境で実行されます。

プレビューが返すWebhookへの送信要求（intent）は最大2件です。実際の送信や、キャプチャした通信に合わせた自動実行は行いません。SHA-256は生成されたパッケージのバイト列から計算し、署名付きの一覧がそのハッシュを認証します。

公開は[公開](publishing.md)、Linuxでの開発は[開発コンテナ](devcontainer.md)を参照してください。
