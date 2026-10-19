---
title: ホーム
lang: ja
layout: home
hero:
  name: "%%REPOSITORY_NAME%%"
  text: '<span lang="en">Frida-like hooks for HTTP traffic</span>'
  tagline: リクエストやレスポンスのJSONを書き換え、通信に合わせて独自のJavaScriptを実行できます。
  image:
    src: /images/interceptor.png
    alt: Interceptor
  actions:
    - theme: brand
      text: プラグインを書く
      link: /authoring
    - theme: alt
      text: Interceptorとは
      link: /what-is-interceptor
features:
  - icon:
      src: /icons/filter.svg
      alt: ""
      wrap: true
      width: 24
      height: 24
    title: 条件に合う通信を処理
    details: ホスト・パス・メソッドで対象を指定できます。条件に一致した通信だけがHookに渡されるため、JavaScriptに同じ条件判定を書く必要はありません。
    link: /api
  - icon:
      src: /icons/json.svg
      alt: ""
      wrap: true
      width: 24
      height: 24
    title: JSONを直接変更
    details: リクエストやレスポンスのJSON本文を、JavaScriptで直接読み書きできます。実際に送るデータの値を差し替えたり、フィールドを追加したりできます。
    link: /authoring
  - icon:
      src: /icons/check.svg
      alt: ""
      wrap: true
      width: 24
      height: 24
    title: テストデータで確認
    details: テスト用のリクエストやレスポンスで、JSONの変更や条件判定を確認できます。実際の通信に適用する前に、プラグインの動作を試せます。
    link: /authoring
  - icon:
      src: /icons/package.svg
      alt: ""
      wrap: true
      width: 24
      height: 24
    title: 署名して配布
    details: 作成したプラグインに署名し、リポジトリで配布できます。利用者はInterceptorにリポジトリのURLを登録し、一覧から必要なプラグインを選んで読み込めます。
    link: /publishing
---
