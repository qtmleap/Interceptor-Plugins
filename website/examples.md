---
title: サンプル
lang: ja
---

<script setup>
import HookFlow from './.vitepress/components/HookFlow.vue'
</script>

# サンプル

処理を書くTypeScriptファイルと、権限を指定する`plugin.json`を載せています。サンプルはいずれも開発中のスキーマ2です。テストの入力と期待値は`fixtures/cases.json`にあります。Webhook形式のアクションは合成テストの結果欄で確認できます。実通信では戻り値を保存・送信しません。

<HookFlow locale="ja" />

## Request summary {#request-summary}

`POST api.example.com/search`を対象にします。`request.onEnter`でJSONの`limit`を`5`へ変更し、`response.onEnter`で`maintenance: true`を追加します。各`onLeave`では転送した内容からテスト用のアクションを作ります。

`plugins/request-summary/hooks/api.example.com/search/POST.ts`

<<< ../plugins/request-summary/hooks/api.example.com/search/POST.ts{ts}

<<< ../plugins/request-summary/plugin.json{json}

このファイルでは1つの`Interceptor.attach`に4つのHookを定義しています。別のAPIにも処理を加える場合は、同じプラグインの`hooks/`以下にファイルを追加します。対象条件とファイルの対応はビルドが生成します。

## Server error filter {#server-error-filter}

`GET https://example.com/`のレスポンスを処理します。ファイルの配置でホスト・パス・メソッドを指定し、Hook内でステータスが5xxかを確認します。5xxの場合だけ、転送前にJSONへ`maintenance: true`を追加し、転送後にホストとステータスを含むテスト用のアクションを返します。

`plugins/server-error-filter/hooks/example.com/GET.ts`

<<< ../plugins/server-error-filter/hooks/example.com/GET.ts{ts}

<<< ../plugins/server-error-filter/plugin.json{json}
