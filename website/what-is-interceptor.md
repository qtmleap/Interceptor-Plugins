---
title: Interceptorとは
lang: ja
---

<script setup>
import HookFlow from './.vitepress/components/HookFlow.vue'
</script>

# Interceptorとは

InterceptorはiPhoneやiPadでHTTP・HTTPS通信の内容を確認するためのアプリです。クライアントとサーバーの間で通信を受け取り、送られたリクエストや返されたレスポンスを記録します。APIの呼び出しやJSONの内容を調べるときに使えます。

HTTPSの内容を確認するには、証明書と対象ホストの設定が必要です。設定手順は[はじめに](getting-started.md)で説明しています。

## Pluginsとは

PluginsはInterceptorで扱う通信にJavaScriptの処理を追加する仕組みです。対象のホスト・パス・メソッドを指定し、条件に合う通信のJSONを書き換えたり、転送後に処理を実行したりできます。

作成した処理はプラグインとしてまとめ、Interceptorに読み込んで使います。署名したプラグインをリポジトリで配布することもできます。

::: info
このガイドで扱う実通信のHookは開発中です。
:::

## どんなことに使えるか

- **リクエストを調整する**: 例えば、検索APIへ送るJSONの`limit`を`50`から`5`に変更します。サーバーは変更後の値を受け取ります。
- **レスポンスを変更する**: APIが返すJSONに`maintenance: true`を追加し、クライアントがその値を受け取ったときの動作を確認できます。
- **条件に合う通信だけを処理する**: 特定のAPIにだけ変更を適用できます。対象条件はInterceptorが判定するため、JavaScript内で同じ条件判定を書く必要はありません。

JSONを書き換える具体例は[プラグインを書く](authoring.md)で紹介しています。

## 仕組み

処理はHookと呼ばれる関数に書きます。リクエストとレスポンスにそれぞれ`onEnter`と`onLeave`があり、`onEnter`で転送前のJSONを書き換え、読み取り専用の`onLeave`で転送後の内容を確認できます。

<HookFlow locale="ja" />

プラグインが扱うのは、Interceptorのプロキシ対象として設定し、利用者がプラグインの適用を承認した通信です。読み取るデータとJSONを書き換える権限はプラグインごとに指定します。Hookの使い方や扱える通信の制限は[APIリファレンス](api.md)を参照してください。

## はじめる

- [はじめに](getting-started.md): 配布されているプラグインを読み込み、テストしてから通信に適用します。
- [プラグインを書く](authoring.md): TypeScriptでJSONを書き換える処理を作り、テストします。
- [公開](publishing.md): 作成したプラグインに署名し、リポジトリで配布します。
