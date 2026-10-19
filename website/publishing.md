---
title: 公開
lang: ja
---

# 公開

自分のリポジトリからプラグインを配布するための手順です。

## 手順

1. **Use this template**から**公開**リポジトリを作り、既定ブランチを **master** に設定してcloneします。直接cloneした場合は、先に `origin` を自分のGitHubリポジトリへ変更してください。
2. 対応するMacで、管理者権限のあるアカウントでGitHub CLIにログインし、次のコマンドを実行します。

   ```sh
   bun install --frozen-lockfile --ignore-scripts
   bun run setup
   bun run check
   ```

   セットアップでは専用のID、Gitの管理対象外に置く署名鍵、master専用のGitHub環境のSecret、GitHub Actionsを使ったPagesへの公開を設定します。commit・push・配布は行いません。秘密鍵と再開用の記録は `~/.config/interceptor/repositories/OWNER--NAME/` に保存されるため、バックアップしてください。
3. `src/NAME.ts`、manifest、期待値を編集し、公開用の設定を含めてcommitし、`master` へpushします。
4. **Publish signed repository** の公開後検証が成功したら、表示された `https://OWNER.github.io/REPO/repository.json` をアプリに登録します。それまでのURLは配布予定先です。

セットアップはリポジトリとプラグインのID、配布URL、公開鍵の指紋を設定ファイルへ書き込みます。これらの公開情報もcommitしてください。組織の権限や追加の保護設定がある場合は、その要件も満たす必要があります。

セットアップが途中で止まった場合は、鍵と再開用の記録を残したまま `bun run setup` を再実行します。同じIDと鍵を再利用するため、原因を調べる際も記録の削除や鍵の再生成はしないでください。所有者を確認できない既存のSecretや鍵は、セットアップでは上書きしません。詳細は下の保守者向け手順を参照してください。

開発用の未署名フィードも使えますが、アプリで未認証リポジトリの確認が必要です。公式の署名付き配布が未署名へ切り替わることはありません。

## 単一の公開

masterのCIが型チェック、JavaScriptへの変換、実際のQuickJSでの検証、SHA-256の生成、署名を行い、1つのGitHub Pagesサイトとして公開します。このドキュメントも同じサイトに含まれます。`repository.json` と `plugins` は署名付きフィードのファイルです。更新のたびに手動で署名する必要はありません。

生成した一覧の有効期限は30日です。masterへのpush、手動実行、週次workflowで更新します。GitHubでは60日間活動がないと定期実行（schedule）が無効になる場合があるため、管理者が実行状態と期限を確認してください。

## 信頼

公開鍵の指紋は信頼できる別の経路でも案内してください。署名の一致だけでは作者の本人確認になりません。

## 保守者向け

鍵の扱い、復旧、公開後の検証などの詳細は[管理・公開手順（docs/maintaining.md）](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/docs/maintaining.md)を参照してください。

## 署名とXcode

プラグインにはEd25519で署名します。Appleのコード署名とは別の処理であり、署名そのものにXcodeが必要なわけではありません。ただし、このテンプレートの `bun run setup` と署名付き公開用ツールは現在Swiftで実装されており、セットアップにはmacOSとXcode 27が必要です。現在の手順では、Bunだけで署名・公開を完了させることはできません。

TypeScriptの編集、型チェック、パッケージ生成、ドキュメントのビルドはXcodeなしでも実行できます。これらを検証する場合は `bun run check:authoring` を使ってください。署名付きで公開する場合は、このページの手順に従ってください。
