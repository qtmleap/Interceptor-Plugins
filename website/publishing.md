---
title: 公開
lang: ja
---

# 公開

自分のリポジトリからプラグインを配布する手順を説明します。

## 手順

1. [GitHubのテンプレートリポジトリ](https://github.com/qtmleap/Interceptor-Plugins)を開き、**Use this template**から新しいリポジトリを作ります。公開範囲は**Public**、既定ブランチは **master** に設定し、作成した自分のリポジトリをcloneします。直接cloneした場合は、まず `origin` を自分のGitHubリポジトリに変更してください。
2. LinuxまたはmacOSで、管理者権限のあるアカウントでGitHub CLIにログインし、次のコマンドを実行します。

   ```sh
   bun install --frozen-lockfile --ignore-scripts
   bun run setup
   bun run check
   ```

   セットアップでは専用のID、Gitの管理対象外に置く署名鍵、master専用のGitHub環境のSecret、GitHub Actionsを使ったPagesへの公開を設定します。commit・push・配布は行いません。秘密鍵と再開用の記録は `~/.config/interceptor/repositories/OWNER--NAME/` に保存されます。バックアップしてください。
3. `src/NAME.ts`、manifest、期待値を編集し、公開用の設定を含めてcommitし、`master` へpushします。
4. **Publish signed repository** の公開後検証が成功したら、表示された `https://OWNER.github.io/REPO/repository.json` をアプリに登録します。それまでのURLは配布予定先です。

セットアップはリポジトリとプラグインのID、配布URL、公開鍵の指紋を設定ファイルへ書き込みます。これらの公開情報もcommitの対象にしてください。組織の権限や追加の保護設定がある場合は、その要件も満たす必要があります。

セットアップが途中で止まった場合は、鍵と再開用の記録を残したまま `bun run setup` を再実行します。同じIDと鍵を再利用するため、原因を調べる際にも記録を削除したり、鍵を再生成したりしないでください。所有者を確認できない既存のSecretや鍵は、セットアップでは上書きしません。詳細は下の保守者向け手順を参照してください。

開発用の未署名フィードも使えますが、アプリで未認証リポジトリの確認が必要です。公式の署名付き配布が未署名へ切り替わることはありません。

## GitHub Actionsによる署名と公開

masterのCIが型チェック、JavaScriptへの変換、実際のQuickJSでの検証、SHA-256の生成、署名を行い、1つのGitHub Pagesサイトとして公開します。このドキュメントも同じサイトに含まれます。`repository.json` と `plugins` は署名付きフィードのファイルです。更新するたびに手動で署名する必要はありません。

生成した一覧の有効期限は30日です。masterへのpush、手動実行、週次workflowで更新します。GitHubでは60日間活動がないと定期実行（schedule）が無効になる場合があるため、管理者が実行状態と期限を確認してください。

## 信頼

公開鍵の指紋は信頼できる別の経路でも案内してください。署名の一致だけでは作者の本人確認になりません。

## 保守者向け

鍵の扱い、復旧、公開後の検証などの詳細は[管理・公開手順（docs/maintaining.md）](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/docs/maintaining.md)を参照してください。

## 署名の仕組み

署名にはBunの暗号機能でEd25519を使います。秘密鍵は32バイトのまま保存し、アプリが検証する署名形式や公開鍵の指紋は従来と同じです。セットアップ、検証、署名付きフィードの生成はLinuxでも実行できます。XcodeやAppleのコード署名は必要ありません。

公開用のGitHub ActionsもUbuntuで動作します。秘密鍵は全検証が成功した後にだけ環境のSecretから復元され、公開物の検証後に削除されます。
