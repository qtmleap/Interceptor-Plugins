# Interceptor Plugins

[English](README.md)

InterceptorのJavaScript試行機能で使える公式サンプルと、配布リポジトリのテンプレートです。通常の `.js` とmanifestを編集し、アプリと同じQuickJSでテストして、署名付きのv1パッケージをHTTPSで配布できます。

## 公式リポジトリを追加する

Pluginsプレビューに対応した **Interceptor 1.1.0以降**で、**設定 → Plugins → ＋ → リポジトリを追加**を開き、次のURLを入力します。

```text
https://qtmleap.github.io/Interceptor-Plugins/repository.json
```

プレビューでソース・宣言・署名鍵の指紋を確認します。初めて見る鍵の署名が正しくても、それだけで公開者の本人確認が済むわけではありません。信頼できる別の経路で指紋全体を照合してからpinしてください。このREADMEとPagesは同じGitHub管理権限の影響を受けるため、このページだけを独立した確認経路とは扱わないでください。

公式公開鍵の指紋: **b29b13755f2df72858c5d14ea7c1b293fa379b9ad3ea2f86f016dfa0735cd96a**

サンプルを選び、ソースを確認して無効状態で読み込みます。読み込んだスクリプトを開き、次のフックを選んで合成データのテストを実行します。

| サンプル | フック | 既定入力で表示されるJSONペイロード |
|---|---|---|
| Request summary | Request | `{"summary":"GET example.com/synthetic"}` |
| Server error filter | Response | `{"host":"example.com","status":503}` |

アクションを返さないケースは、レスポンスのテスト入力のステータスを `200` に変えて確認できます。フックはサンプルに合わせて選択してください。Request専用のサンプルに `onResponse` は定義していません。

現在のプレビューは、明示的に渡した合成入力で実行し、返されたアクションを表示します。サンプルを実キャプチャへ自動接続したり、バックグラウンドで実行したり、Webhookへ送信したりはしません。読み込み時は無効状態で保存します。この2本は本文・ヘッダー・クエリ値を要求しません。

## ローカルでテストする

検証にはXcode 27.0（Swift 6.4）が使えるMac、Python 3、Gitを使います。利用するSwift packageのdeployment targetはmacOS 14のままですが、古い既定のSwiftコンパイラでは固定した実行基盤をビルドできません。リポジトリのルートで実行します。

```sh
tools/check.sh
```

固定した公開Interceptorソースを取得し、既存publisherとQuickJS検証ツールをビルドします。パッケージ生成の再現性、リクエスト・レスポンスの期待値、テスト用の一時鍵による署名と改変検知を確認します。公式の秘密鍵は使わず、公開処理も行いません。

編集するソースは `scripts/` と `manifests/`、入出力の期待値は `fixtures/` にあります。`build/site/` はGit管理対象外の生成物です。実行基盤の固定SHAは `repository-config.json` に記録し、QuickJSや暗号処理はコピーしていません。

## 自分の配布リポジトリを作る

1. **Use this template**から自分の名前のリポジトリを作り、cloneします。初期設定は公式配布先のものなので、署名配布する前に変更します。
2. checkoutとWeb公開ディレクトリの外に、自分用の鍵を生成します。安全な場所にバックアップし、Gitへ含めないでください。

   ```sh
   tools/bootstrap.sh
   mkdir -p ~/.config/interceptor
   swift run --package-path .tools/interceptor/Packages/InterceptorAutomation \
     interceptor-repository keygen ~/.config/interceptor/my-plugins.key
   ```

   表示されるのは公開鍵の指紋です。秘密鍵そのものは表示しません。

3. 名前、配布URL、上で表示された指紋を自分用に設定します。リポジトリとサンプルのUUIDも新しく割り当てます。

   ```sh
   python3 tools/configure.py --root . \
     --repository YOUR_NAME/YOUR_REPO --name "My plugins" \
     --url https://YOUR_NAME.github.io/YOUR_REPO/repository.json \
     --fingerprint YOUR_64_HEX_FINGERPRINT
   ```

4. スクリプトとmanifestを編集し、バージョンと期待値を更新して `tools/check.sh` を実行します。v1パッケージとアクションの形式を維持してください。
5. [管理・公開手順](docs/maintaining.md)に従ってmaster専用の署名environment、自分のSecret、Pagesを設定し、公開URLを検証します。指紋は別の信頼できる経路でも案内してください。

開発用の未署名出力も利用できます。アプリでは未認証リポジトリの確認が必要です。SHA-256は一覧とパッケージの不一致を検知しますが、未署名サーバーでは両方を書き換えられます。公式配布では鍵がない場合に失敗し、未署名へ切り替えません。

## 運用

生成した一覧の有効期限は30日です。masterへのpush、手動実行、週次workflowで更新します。GitHubでは60日間リポジトリに活動がないとscheduleが無効になる場合があるため、管理者が実行状態と一覧の期限を確認する必要があります。[鍵の扱い・復旧・公開検証](docs/maintaining.md)を参照してください。

MITライセンスです。利用するInterceptorのツールとvendored QuickJSは、それぞれ上流のライセンスを維持します。
