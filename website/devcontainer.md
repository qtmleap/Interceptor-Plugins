---
title: 開発環境
lang: ja
---

# 開発環境

## 使い方

DockerとVS Code、Dev Containers拡張機能を用意し、Dockerを起動します。このリポジトリのルートフォルダーをVS Codeで開き、コマンドパレットから **Dev Containers: Reopen in Container** を実行します。依存関係のインストールには `bun install --frozen-lockfile --ignore-scripts` を使います。プラグインの開発にXcodeは不要です。

`plugins/NAME/hooks/{host}/{path}/{METHOD}.ts`に処理を書き、次のコマンドで生成・検証します。ファイルの構成とHookの例は[プラグインを書く](authoring.md)を参照してください。

```sh
bun run build
bun run simulator check build/scripts/request-summary/hooks/api.example.com/search/POST.js
bun run simulator run-package build/dev/plugins/request-summary.json request.onEnter fixtures/request-event.json fixtures/config.json
bun run check:authoring
```

`build`は未署名のパッケージを`build/dev/plugins/`に生成します。ソースを変更するたびに再実行できます。コンパイルやパッケージ生成に失敗した場合は、`build/dev/`の前回のパッケージを残します。内部の`build/scripts/`と`build/manifests/`もビルドで再生成されるため、パッケージ生成に失敗しても更新されている場合があります。

シミュレーターの`check`は生成されたJavaScriptの構文を、`run-package`はパッケージ内のHookの実行結果を確認します。

VS Codeでは各HookファイルにSDKの型が適用され、JavaScriptは出力されません。ビルド用と検証用のタスクも選べます。ファイルの配置や使える構文の最終確認には`build`と`check:authoring`を使います。

`bun run check`は署名と改ざん検出も検証します。テストには一時的な鍵を使うので、GitHubの認証情報や公開用の署名鍵は不要です。`build:dev`は互換用の別名として残しています。

新しいリポジトリの署名鍵・GitHub Environment・Pagesを設定するときは、コンテナ内で `gh auth login` を済ませてから `bun run setup` を実行します。手順は[公開](publishing.md)を参照してください。

## 認証で初期設定が止まった場合

プラグインのビルド・検証自体にはGitHubの認証情報は不要です。ただし、この開発環境の初期設定では、Git操作を保護するcommit guardの認証確認で停止する場合があります。

実行中のコンテナに接続し、その中で次のコマンドを実行します。GitHubへのログイン後、`commitguard/setup`でGit操作に必要な認証確認をやり直し、`postCreateCommand.sh`で依存関係をインストールする初期設定を再開します。

```sh
cd /home/vscode/app
gh auth login -h github.com
/usr/local/share/commitguard/setup
bash .devcontainer/postCreateCommand.sh
```

## 認証情報と鍵

- commit guardは人間のGitHubアカウントでログイン済みかを確認します。認証が完了するまでGitの操作はブロックされます。認証で止まった場合は、実行中のコンテナ内で `gh auth login -h github.com` の後に `/usr/local/share/commitguard/setup` を実行します。
- ホストの認証情報や署名鍵はマウントしません。ただしVS Code自身がGit設定、credential helper、SSH agentを転送する場合があります。分離が必要なら該当のVS Code設定を確認してください。

詳細な構成と上流のライセンスは[docs/devcontainer.md](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/docs/devcontainer.md)にあります。
