---
title: サンプル
lang: ja
---

<script setup>
import HookFlow from './.vitepress/components/HookFlow.vue'
</script>

# サンプル

処理を書くTypeScriptファイルと、権限を指定する`plugin.json`を載せています。サンプルはいずれも開発中のスキーマ2です。テストの入力と期待値は`fixtures/cases.json`にあります。以下の`webhook`アクションは合成テストの出力形式です。実際のHTTP送信は行わず、実通信でも戻り値を保存・送信しません。

<HookFlow locale="ja" />

## Request summary {#request-summary}

Request summaryはJSONを書き換え、転送後の情報からテスト用の要約アクションを作る例です。`POST api.example.com/search`を対象にします。`request.onEnter`でJSONの`limit`を`5`へ変更し、`response.onEnter`で`maintenance: true`を追加します。各`onLeave`では転送した内容からテスト用のアクションを作ります。

`plugins/request-summary/hooks/api.example.com/search/POST.ts`

<<< ../plugins/request-summary/hooks/api.example.com/search/POST.ts{ts}

<<< ../plugins/request-summary/plugin.json{json}

このファイルでは1つの`Interceptor.attach`に4つのHookを定義しています。別のAPIにも処理を加える場合は、同じプラグインの`hooks/`以下にファイルを追加します。対象条件とファイルの対応はビルドが生成します。

## Server error filter {#server-error-filter}

Server error filterの「filter」は、5xxの場合だけ処理するという意味です。エラーを除去したり通信を遮断したりするものではありません。`GET https://example.com/`のレスポンスを処理します。ファイルの配置でホスト・パス・メソッドを指定し、Hook内でステータスが5xxかを確認します。5xxの場合だけ、転送前にJSONへ`maintenance: true`を追加し、転送後にホストとステータスを含むテスト用のアクションを返します。

`plugins/server-error-filter/hooks/example.com/GET.ts`

<<< ../plugins/server-error-filter/hooks/example.com/GET.ts{ts}

<<< ../plugins/server-error-filter/plugin.json{json}

## Outbound example {#outbound-example}

`fixtures/`にある開発用のサンプルです。公開用の標準プラグインには含まれません。`GET https://interceptor-traffic-fixture.lemonandchan.workers.dev/auth/credentials`の`200`レスポンスから、JSONの`accessToken`と、読み取りを許可した`set-cookie`を取得します。`response.onLeave`から`Interceptor.send`を呼び、`/auth/bearer`へは取得したトークンを認証ヘッダーに付けて、`/auth/cookie`へは取得したCookieを付けてGETリクエストを送ります。送信先は`outbound`で固定されています。

この公開テスト用APIが返す値は、`accessToken: "interceptor-test-token"`と`fixture_session=dummy-session-not-a-secret`です。Cookieは`Set-Cookie`の最初のペアだけを取り出し、`Path`などの属性を除いて渡します。このサンプルをシミュレータで実行しても、別APIへのGETリクエストは送信しません。

`fixtures/outbound-example/hooks/interceptor-traffic-fixture.lemonandchan.workers.dev/auth/credentials/GET.ts`

<<< ../fixtures/outbound-example/hooks/interceptor-traffic-fixture.lemonandchan.workers.dev/auth/credentials/GET.ts{ts}

<<< ../fixtures/outbound-example/plugin.json{json}
