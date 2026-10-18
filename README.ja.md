# Interceptor Plugins

[English](README.md)

InterceptorのJavaScript試行機能で使える公式サンプルと、配布リポジトリのテンプレートです。TypeScriptの `.ts` とmanifestを編集し、生成したJavaScriptをアプリと同じQuickJSでテストして、署名付きのv1パッケージをHTTPSで配布できます。

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

検証にはXcode 27.0（Swift 6.4）が使えるMac、Node.js（`.node-version` のバージョン）、Python 3、Gitを使います。利用するSwift packageのdeployment targetはmacOS 14のままですが、古い既定のSwiftコンパイラでは固定した実行基盤をビルドできません。リポジトリのルートで実行します。

```sh
npm ci --ignore-scripts
npm run check
```

固定した公開Interceptorソースを取得し、既存publisherとQuickJS検証ツールをビルドします。パッケージ生成の再現性、リクエスト・レスポンスの期待値、テスト用の一時鍵による署名と改変検知を確認します。公式の秘密鍵は使わず、公開処理も行いません。

編集するソースは `src/*.ts` と `manifests/`、入出力の期待値は `fixtures/` にあります。パッケージ生成時は毎回、型チェックとJavaScriptへの変換を行います。`build/scripts/` と `build/site/` はGit管理対象外の生成物です。フックの型と実行環境の制約は[TypeScriptの書き方](docs/authoring.md)を参照してください。実行基盤の固定SHAは `repository-config.json` に記録し、QuickJSや暗号処理はコピーしていません。

## 自分の配布リポジトリを作る

1. **Use this template**から自分の公開リポジトリを作り、既定ブランチを **master** にしてcloneします。直接cloneした場合は、先に `origin` を自分のGitHubリポジトリへ変更してください。
2. 対応するMacでGitHub CLIに管理者権限のあるアカウントでログインし、実行します。

   ```sh
   npm ci --ignore-scripts
   npm run setup
   npm run check
   ```

   セットアップが専用のリポジトリ／プラグインIDと署名鍵を作り、master専用のenvironmentにSecretを保存し、Pagesと公開workflowを設定します。既存の保護設定は維持し、不明な鍵・Secretや公式checkoutの上書きは拒否します。秘密鍵と再開用の記録は `~/.config/interceptor/repositories/OWNER--NAME/` に保存します。このディレクトリは安全な場所へバックアップしてください。再実行しても同じ鍵とIDを使います。セットアップ自体はcommit・push・配布を行いません。
3. `src/NAME.ts`、manifest、期待値を編集し、公開用の設定・TypeScript・manifest・テストをcommitしてmasterへpushします。CIが型チェック、変換、実際のQuickJSでの検証、SHA-256の生成、署名、配布を行います。更新ごとの手動署名は不要です。
4. **Publish signed repository**の公開後検証まで成功したら、表示された `https://OWNER.github.io/REPO/repository.json` をアプリへ登録できます。セットアップ直後のURLは配布予定先です。公開鍵の指紋は、信頼できる別の経路でも案内してください。署名の一致だけでは作者の本人確認はできません。

初回はPages・environment・Secretを設定するためのGitHub管理権限が必要です。通常のCIトークンだけでは初回の認証設定は行えません。組織の制限がある場合は管理者による設定が必要です。既存リポジトリの設定や復旧は[管理・公開手順](docs/maintaining.md)を参照してください。

開発用の未署名出力も利用できます。アプリでは未認証リポジトリの確認が必要です。SHA-256は一覧とパッケージの不一致を検知しますが、未署名サーバーでは両方を書き換えられます。公式配布では鍵がない場合に失敗し、未署名へ切り替えません。

## 運用

生成した一覧の有効期限は30日です。masterへのpush、手動実行、週次workflowで更新します。GitHubでは60日間リポジトリに活動がないとscheduleが無効になる場合があるため、管理者が実行状態と一覧の期限を確認する必要があります。[鍵の扱い・復旧・公開検証](docs/maintaining.md)を参照してください。

MITライセンスです。利用するInterceptorのツールとvendored QuickJSは、それぞれ上流のライセンスを維持します。
