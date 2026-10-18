---
title: TypeScriptの書き方
lang: ja
---

# TypeScriptの書き方

## ファイルの構成

`src/NAME.ts`、`manifests/NAME.json`、`fixtures/cases.json` を一緒に編集します。ソースにはそれぞれ、同じ小文字kebab-caseの名前のmanifestが必要です。リポジトリ／プラグインのIDは初回セットアップ後は変えません。

## 必要なツール

Bun %%BUN_VERSION%%、Python 3、OpenSSL、Gitを使います。全検証の `bun run check` には、Xcode 27 / Swift 6.4を選択したMacが必要です。Linuxでは `check:authoring` を実行できます。

## プラグインを追加する

既存のTypeScriptとmanifestをコピーし、同じ新しい小文字kebab-caseのファイル名に揃えます。manifestの `id` には重複しないUUIDを一度生成し、公開後は維持します。

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
- `bun run build` の出力先 `build/site/` は、存在しないか空である必要があります。前回の生成物だけを削除してから再実行してください。
- `build/scripts/` の生成JavaScriptは編集もcommitもしません。パッケージ生成のたびにTypeScriptから再生成されます。
- 署名鍵はテスト後にpublishing workflowが用意します。手元で署名する必要はありません。

## バージョンを更新する

ソース、生成されるバイト列、型宣言のいずれかを変えたら、manifestの `version` を上げます。サンプルはv1 manifestのバージョン 1.0.1 です。アプリ側の新しいスキーマは不要です。

## フックを書く

トップレベル関数 `onRequest` または `onResponse` を、manifestの購読に合わせて定義します。各プラグインは独立してコンパイルされるため、ファイル間で関数名が重複しても構いません。

<<< ../src/request-summary.ts{ts}

このサンプルはテスト用の `preview` バインディングと入力を使います。新しいフックでは、バインディングと任意の入力項目が存在することを確認し、必要な値がなければ `{ actions: [] }` を返してください。

型は [APIリファレンス](api.md) を参照してください。

## 実行環境の制約

ランタイムは1つのグローバルスクリプトを評価し、フックを同期的に呼びます。import/export、非同期コード、Promise、TypedArray、Node／ブラウザAPIは使えません。`fetch`、console、ファイルシステム、タイマー、モジュールローダーもありません。コンパイラはこれらの一般的な構文を拒否しますが、セキュリティサンドボックスではありません。実行の境界はアプリの制限付きQuickJSです。

プレビューが返すWebhook intentは最大2件で、送信はせず、キャプチャへ自動接続もしません。SHA-256は生成されたパッケージのバイト列を対象とし、署名付き一覧がそのハッシュを認証します。

公開は[公開](publishing.md)、Linuxでの開発は[開発コンテナ](devcontainer.md)を参照してください。
