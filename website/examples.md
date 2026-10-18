---
title: サンプル
lang: ja
---

# サンプル

リポジトリに含まれる実際のファイルを表示しています。

長いコードはコード枠の中を横にスクロールして読めます。コード枠のコピー操作で全文を取得できます。

## Request summary

`GET example.com` のリクエスト完了時に、`GET example.com/path` 形式の要約を返します。

<<< ../src/request-summary.ts{ts}

<<< ../manifests/request-summary.json{json}

## Server error filter

`example.com` の5xxレスポンスだけを対象に、ホストとステータスを返します。

<<< ../src/server-error-filter.ts{ts}

<<< ../manifests/server-error-filter.json{json}

どちらも本文・ヘッダー・クエリ値を読まず（`body.mode` は `none`）、`preview` バインディングだけを使います。合成テストはmanifestのフィルターを適用しないため、ソース内でもメソッド、ホスト、ステータスを確認しています。
