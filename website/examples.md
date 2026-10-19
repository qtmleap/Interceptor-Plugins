---
title: サンプル
lang: ja
---

# サンプル

「Request summary」と「Server error filter」は、リポジトリに含まれる実際の既存サンプルです。末尾の将来設計は未実装で、実行できるものとして示していません。

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

## 将来のHTTP Hook設計（未実装） {#future-http-hooks}

::: info 未実装のAPI
このセクションは**将来の設計**です。`Interceptor.attach` と `rewriteJsonBody` は現在存在せず、現在の合成テストでは動きません。`rewriteJsonBody` は実行環境が提供する想定の組み込み関数で、作者が定義やimportをする必要はありません。
:::

1つのプラグインソースに `POST /search` と `GET /status` の二つの `attach` を含める設計例です。それぞれの `Interceptor.attach` を同じソースのトップレベルに並べます。プラグイン全体で `id` / `version` は1組です。詳細は[HTTP Hook設計](api.md#http-hooks)を参照してください。

```javascript
Interceptor.attach({
  hosts: ["api.example.com"],
  methods: ["POST"],
  path: { kind: "exact", value: "/search" }
}, {
  request: {
    onEnter(request) {
      rewriteJsonBody(request, (data) => {
        data.limit = 5;
        data.locale = "ja-JP";
      });
    },
    onLeave(request) {
      // 検索リクエストを送った後の処理を書く
    }
  },
  response: {
    onEnter(response) {
      // 検索結果を元のアプリへ返す前の処理を書く
    },
    onLeave(response) {
      // 検索結果を元のアプリへ返した後の処理を書く
    }
  }
});

Interceptor.attach({
  hosts: ["api.example.com"],
  methods: ["GET"],
  path: { kind: "exact", value: "/status" }
}, {
  request: {
    onEnter(request) {
      // 状態確認リクエストを送る前の処理を書く
    },
    onLeave(request) {
      // 状態確認リクエストを送った後の処理を書く
    }
  },
  response: {
    onEnter(response) {
      rewriteJsonBody(response, (data) => {
        data.maintenance = true;
        data.message = "ただいまメンテナンス中です";
      });
    },
    onLeave(response) {
      // 状態確認レスポンスを元のアプリへ返した後の処理を書く
    }
  }
});
```
