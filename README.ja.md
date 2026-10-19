# Interceptor Plugins

[English](README.md)

ドキュメント: [日本語](https://qtmleap.github.io/Interceptor-Plugins/) / [English](https://qtmleap.github.io/Interceptor-Plugins/en/)

Interceptorの通信にJavaScriptの処理を追加する公式サンプルと、配布リポジトリのテンプレートです。ホスト・パス・メソッドなどで対象を指定し、送信前のリクエストや返却前のレスポンスのJSONを変更できます。転送成功後に呼ぶHookも用意しています。TypeScriptとスキーマ2のmanifestを編集し、アプリと共通のQuickJSで検証して、署名付きパッケージとして配布できます。

## 公式リポジトリを追加する

スキーマ2と4つのHookに対応したInterceptorで、**設定 → Plugins → ＋ → リポジトリを追加**を開き、次のURLを入力します。

```text
https://qtmleap.github.io/Interceptor-Plugins/repository.json
```

追加前のプレビューでリポジトリ名と署名鍵の指紋を確認します。ソースとmanifestは、追加後にスクリプトの詳細画面で確認できます。初めて見る鍵の署名が正しくても、それだけで公開者の本人確認が済むわけではありません。信頼できる別の経路で指紋全体を照合してから、署名鍵を信頼する操作を行ってください。このREADMEとPagesは同じGitHub管理権限の影響を受けるため、このページだけを別経路の確認に使わないでください。

公式公開鍵の指紋: **b29b13755f2df72858c5d14ea7c1b293fa379b9ad3ea2f86f016dfa0735cd96a**

サンプルを選び、ソースと権限を確認して無効状態で読み込みます。詳細画面でHookと入力JSONを選び、合成テストを実行します。合成テストは通信やWebhookを送信せず、JSON本文の変更と返されたアクションを表示します。

### Request summary

`request.onEnter`は`POST api.example.com/search`のJSON本文の`limit`を`5`へ変更します。`response.onEnter`は対応するレスポンスに`maintenance: true`を追加します。各`onLeave`は転送後の内容からテスト用のアクションを作ります。

### Server error filter

`example.com`のステータス500〜599のレスポンスを対象に、`response.onEnter`でJSONに`maintenance: true`を追加し、`response.onLeave`で結果を作ります。ステータスを`200`に変えると対象から外れます。

実通信で使うときは、利用者がソースと権限を確認し、対象のリビジョンを承認します。読み込みや編集だけでは有効になりません。実通信ではアクションを保存・送信しません。[設定手順](website/getting-started.md)と[4つのHookの図・説明](website/index.md)を参照してください。

## コンテナで開発する

[qtmleap/devcontainersを基にした開発環境](docs/devcontainer.md)を用意しています。VS Codeの **Dev Containers: Reopen in Container** で開き、`bun run check`で型チェック、QuickJSの実行、署名付きフィードの検証を実行できます。初回の署名セットアップと配布もLinuxで行えます。

## ローカルでテストする

LinuxまたはmacOSで、Bun（`.bun-version`のバージョン）、Python 3、OpenSSL、Git、Rust 1.74以降、Cコンパイラを使います。Xcodeは不要です。リポジトリのルートで実行します。

```sh
bun install --frozen-lockfile --ignore-scripts
bun run check
```

固定した公開Interceptorソースを取得し、共通のQuickJSブリッジを使うRust製シミュレーターをビルドします。パッケージ生成の再現性、リクエスト・レスポンスの期待値、テスト用の一時鍵による署名と改変検知を確認します。公式の秘密鍵は使わず、公開処理も行いません。

編集するソースは `src/*.ts` と `manifests/`、入出力の期待値は `fixtures/` にあります。パッケージ生成時は毎回、型チェックとJavaScriptへの変換を行います。`build/scripts/` と `build/site/` はGit管理対象外の生成物です。フックの型と実行環境の制約は[作成ガイド](website/authoring.md)を参照してください。実行基盤の固定SHAは `repository-config.json` に記録し、QuickJSはそのSHAから取得し、Ed25519の署名にはBunの暗号機能を使います。

## シミュレーター

```sh
bun run simulator check build/scripts/request-summary.js
bun run simulator run build/scripts/request-summary.js request.onEnter fixtures/request-event.json fixtures/config.json --manifest manifests/request-summary.json
```

先に`bun run check`を実行してJavaScriptを生成します。`check`はスクリプトを実行せず構文を検査し、`run`は指定した1つのHookを実行してアクションと本文変更をJSONで返します。ビルドした`.tools/bin/interceptor-simulator`は対象のOS・CPU向けの単体バイナリとして実行できます。詳しくは[作成ガイド](website/authoring.md)を参照してください。

## 自分の配布リポジトリを作る

1. **Use this template**から自分の公開リポジトリを作り、既定ブランチを **master** にしてcloneします。直接cloneした場合は、先に `origin` を自分のGitHubリポジトリへ変更してください。
2. LinuxまたはmacOSで、GitHub CLIにリポジトリ管理権限のあるアカウントでログインし、実行します。

   ```sh
   bun install --frozen-lockfile --ignore-scripts
   bun run setup
   bun run check
   ```

   セットアップが専用のリポジトリ／プラグインIDと署名鍵を作り、master専用のenvironmentにSecretを保存し、Pagesと公開workflowを設定します。既存の保護設定は維持し、不明な鍵・Secretや公式checkoutの上書きは拒否します。秘密鍵と再開用の記録は `~/.config/interceptor/repositories/OWNER--NAME/` に保存します。このディレクトリは安全な場所へバックアップしてください。再実行しても同じ鍵とIDを使います。セットアップ自体はcommit・push・配布を行いません。
3. `src/NAME.ts`、manifest、期待値を編集し、公開用の設定・TypeScript・manifest・テストをcommitしてmasterへpushします。CIが型チェック、変換、実際のQuickJSでの検証、SHA-256の生成、署名、配布を行います。更新ごとの手動署名は不要です。
4. **Publish signed repository**の公開後検証まで成功したら、表示された `https://OWNER.github.io/REPO/repository.json` をアプリへ登録できます。セットアップ直後のURLは配布予定先です。公開鍵の指紋は信頼できる別の経路でも案内してください。署名の一致だけでは作者の本人確認はできません。

初回はPages・environment・Secretを設定するためのGitHub管理権限が必要です。通常のCIトークンだけでは初回の認証設定は行えません。組織の制限がある場合は管理者による設定が必要です。既存リポジトリの設定や復旧は[管理・公開手順](docs/maintaining.md)を参照してください。

開発用の未署名出力も利用できます。アプリでは未認証リポジトリの確認が必要です。SHA-256は一覧とパッケージの不一致を検知しますが、未署名サーバーでは両方を書き換えられます。公式配布では鍵がない場合に失敗し、未署名へ切り替えません。

## 運用

生成した一覧の有効期限は30日です。masterへのpush、手動実行、週次workflowで更新します。GitHubでは60日間リポジトリに活動がないとscheduleが無効になる場合があるため、管理者が実行状態と一覧の期限を確認する必要があります。[鍵の扱い・復旧・公開検証](docs/maintaining.md)を参照してください。

MITライセンスです。利用するInterceptorのツールとvendored QuickJSは、それぞれ上流のライセンスを維持します。
