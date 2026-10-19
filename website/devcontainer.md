---
title: 開発コンテナ
lang: ja
---

# 開発コンテナ

`qtmleap/devcontainers` を基に構築した開発環境です。Ubuntu 24.04、Bun %%BUN_VERSION%%、Python 3、OpenSSL、GitHub CLIを含みます。

## 使い方

DockerとVS Codeを用意し、**Dev Containers: Reopen in Container** で開きます。依存関係は `bun install --frozen-lockfile --ignore-scripts` でインストールします。

```sh
bun run check:authoring
bun run build
```

`check:authoring` はPythonツールのテスト、HTTPSの検証、TypeScriptの型チェックを行い、同じ入力から同じパッケージを生成します。GitHubの認証情報や署名鍵は不要です。出力先の `build/site/` は存在しないか空である必要があります。

## 認証で初期設定が止まった場合

実行中のコンテナに接続し、その中で次のコマンドを実行します。ログイン後に初期設定を再開するため、最後のコマンドまで進めてください。

```sh
cd /home/vscode/app
gh auth login -h github.com
/usr/local/share/commitguard/setup
bash .devcontainer/postCreateCommand.sh
```

## 制限

- 実際のQuickJS、署名、テンプレート全体の検証を行う `bun run check` には、Xcode 27 / Swift 6.4のMacが必要です。この検証はCIでも署名・公開の前に必須で、Linuxの検証では代替できません。
- 初回の `bun run setup` もCryptoKitを使うためMacで行います。対応していないホストでは、状態を変更する前に実行が拒否されます。
- commit guardは人間のGitHubアカウントでログイン済みかを確認します。認証が済むまでGitの操作はブロックされます。認証で止まった場合は、実行中のコンテナ内で `gh auth login -h github.com` の後に `/usr/local/share/commitguard/setup` を実行します。
- ホストの認証情報や署名鍵はマウントしません。ただしVS Code自身がGit設定、credential helper、SSH agentを転送する場合があります。分離が必要なら該当のVS Code設定を確認してください。

詳細な構成と上流のライセンスは[docs/devcontainer.md](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/docs/devcontainer.md)にあります。
