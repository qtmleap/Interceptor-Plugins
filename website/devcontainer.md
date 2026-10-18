---
title: 開発コンテナ
lang: ja
---

# 開発コンテナ

`qtmleap/devcontainers` を基にした開発環境です。Ubuntu 24.04、Bun %%BUN_VERSION%%、Python 3、OpenSSL、GitHub CLIを含みます。

## 使い方

DockerとVS Codeを用意し、**Dev Containers: Reopen in Container** で開きます。依存関係は `bun install --frozen-lockfile --ignore-scripts` で入ります。

```sh
bun run check:authoring
bun run build
```

`check:authoring` はPythonツールのテスト、HTTPSの検証、TypeScriptの型チェック、決定的なパッケージ生成を行います。GitHubの認証情報や署名鍵は不要です。`build/site/` は存在しないか空である必要があります。

## 認証で初期設定が止まった場合

実行中のコンテナに接続し、同じコンテナ内で次を実行します。ログイン後に初期設定を再開するため、最後のコマンドまで進めてください。

```sh
cd /home/vscode/app
gh auth login -h github.com
/usr/local/share/commitguard/setup
bash .devcontainer/postCreateCommand.sh
```

## 制限

- 実QuickJS、署名、テンプレート全体の検証 `bun run check` はXcode 27 / Swift 6.4のMacで行います。CIでも署名・公開の前に必須で、Linuxの検証では代替できません。
- 初回の `bun run setup` もMacで行います（CryptoKitを使うため）。非対応ホストでは状態を変更する前に拒否されます。
- commit guardは確認済みの人間のGitHubログインを必要とし、認証が済むまでGitをブロックします。認証で止まった場合は、実行中のコンテナ内で `gh auth login -h github.com` の後に `/usr/local/share/commitguard/setup` を実行します。
- ホストの認証情報や署名鍵はマウントしません。ただしVS Code自身がGit設定、credential helper、SSH agentを転送する場合があります。分離が必要なら該当のVS Code設定を確認してください。

詳細な構成と上流のライセンスは[docs/devcontainer.md](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/docs/devcontainer.md)にあります。
