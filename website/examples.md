---
title: サンプル
lang: ja
---

# サンプル

このリポジトリの「Request summary」と「Server error filter」は、現在の合成テストで実行できるサンプルです。

長いコードはコード枠を横にスクロールして確認できます。コピーするとコード全文を取得できます。

## Request summary

`GET example.com` のリクエスト完了時に、`GET example.com/path` 形式の要約を返します。

<<< ../src/request-summary.ts{ts}

<<< ../manifests/request-summary.json{json}

## Server error filter

`example.com` の5xxレスポンスだけを対象に、ホストとステータスを返します。

<<< ../src/server-error-filter.ts{ts}

<<< ../manifests/server-error-filter.json{json}

どちらのサンプルも本文・ヘッダー・クエリ値を読み取らず（`body.mode` は `none`）、`preview` バインディングだけを使います。合成テストはmanifestのフィルターを適用しないため、ソース内でもメソッド、ホスト、ステータスを確認しています。
