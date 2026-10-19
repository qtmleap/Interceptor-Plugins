---
title: サンプル
lang: ja
---

<script setup>
import HookFlow from './.vitepress/components/HookFlow.vue'
</script>

# サンプル

ソースとmanifestを同じページに載せています。サンプルはいずれもスキーマ2です。テストの入力と期待値は`fixtures/cases.json`にあります。Webhookアクションは合成テストの結果欄で確認するための送信要求です。実通信では戻り値を保存・送信しません。

<HookFlow locale="ja" />

## Request summary {#request-summary}

`POST api.example.com/search`を対象にします。`request.onEnter`でJSONの`limit`を`5`へ変更し、`response.onEnter`で`maintenance: true`を追加します。各`onLeave`では転送した内容から送信要求を作ります。

<<< ../src/request-summary.ts{ts}

<<< ../manifests/request-summary.json{json}

`Interceptor.attach`を処理ごとに並べても、1つの呼び出しに4つのHookを書いても構いません。対象条件はmanifestの`matches`と同じ内容にします。

## Server error filter {#server-error-filter}

`example.com`の5xxレスポンスを対象にします。ステータスの条件は対象判定で確認するため、Hook内の条件分岐は不要です。転送前にJSONへ`maintenance: true`を追加し、転送後にホストとステータスを含む送信要求を返します。

<<< ../src/server-error-filter.ts{ts}

<<< ../manifests/server-error-filter.json{json}
