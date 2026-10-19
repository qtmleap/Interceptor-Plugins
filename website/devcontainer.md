---
title: 開発コンテナ
lang: ja
---

# 開発コンテナ

`qtmleap/devcontainers` を基に構築した開発環境です。Ubuntu 24.04、Bun %%BUN_VERSION%%、Python 3、OpenSSL、GitHub CLI、Rust、Cコンパイラを含みます。

## 使い方

DockerとVS Codeを用意して、**Dev Containers: Reopen in Container** で開きます。依存関係のインストールには `bun install --frozen-lockfile --ignore-scripts` を使います。

```sh
bun run check
bun run build
```

`check` は型チェック、パッケージ生成、QuickJSでの実行、署名と改ざん検出を検証します。テストには一時的な鍵を使うので、GitHubの認証情報や公開用の署名鍵は不要です。出力先の `build/site/` は存在しないか空である必要があります。

新しいリポジトリの署名鍵・GitHub環境・Pagesを設定するときは、コンテナ内で `gh auth login` を済ませてから `bun run setup` を実行します。手順は[公開](publishing.md)を参照してください。

## 認証で初期設定が止まった場合

実行中のコンテナに接続し、その中で次のコマンドを実行します。ログイン後に初期設定を再開できるよう、最後のコマンドまで実行してください。

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
