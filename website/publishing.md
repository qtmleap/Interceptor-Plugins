---
title: 公開
lang: ja
---

# 公開

自分の配布リポジトリを作る手順です。

## 手順

1. **Use this template**から**公開**リポジトリを作り、既定ブランチを **master** にしてcloneします。直接cloneした場合は、先に `origin` を自分のGitHubリポジトリへ変更してください。
2. 対応するMacで、管理者権限のあるアカウントでGitHub CLIにログインし、実行します。

   ```sh
   bun install --frozen-lockfile --ignore-scripts
   bun run setup
   bun run check
   ```

   セットアップは専用のID、署名鍵（Gitの外）、master専用のenvironment Secret、Pages（Actions）を設定します。commit・push・配布は行いません。秘密鍵と再開用の記録は `~/.config/interceptor/repositories/OWNER--NAME/` にあるため、バックアップしてください。
3. `src/NAME.ts`、manifest、期待値を編集し、公開用の設定を含めてcommitし、`master` へpushします。
4. **Publish signed repository** の公開後検証が成功したら、表示された `https://OWNER.github.io/REPO/repository.json` をアプリに登録します。それまでのURLは配布予定先です。

セットアップはリポジトリとプラグインのID、配布URL、公開鍵の指紋を設定ファイルへ書き込みます。これらの公開情報もcommitしてください。組織の権限や追加の保護設定がある場合は、その要件も満たす必要があります。

途中で止まった場合は、鍵と再開用の記録を残したまま `bun run setup` を再実行します。同じIDと鍵を再利用するため、問題の切り分けで記録を削除したり鍵を生成し直したりしないでください。所有者を確認できない既存のSecretや鍵は上書きしません。詳細は下の保守者向け手順を参照してください。

開発用の未署名フィードも使えますが、アプリで未認証リポジトリの確認が必要です。公式の署名付き配布が未署名へ切り替わることはありません。

## 単一の公開

masterのCIが型チェック、変換、実QuickJSの検証、SHA-256の生成、署名を行い、1つのGitHub Pagesとして公開します。このサイトも同じ公開物に含まれ、`repository.json` と `plugins` は署名付きフィードのものです。更新ごとの手動署名は不要です。

生成した一覧の有効期限は30日です。masterへのpush、手動実行、週次workflowで更新します。GitHubは60日間活動がないとscheduleを無効にすることがあるため、管理者が実行状態と期限を確認してください。

## 信頼

公開鍵の指紋は、信頼できる別の経路でも案内してください。署名の一致だけでは作者の本人確認になりません。

## 保守者向け

鍵の扱い、復旧、公開後の検証などの詳細は、[管理・公開手順（docs/maintaining.md）](https://github.com/%%GITHUB_REPOSITORY%%/blob/master/docs/maintaining.md)を参照してください。

## 署名とXcode

プラグインの署名はEd25519によるデータの署名で、Appleのコード署名とは別です。署名処理そのものにXcodeが必要なわけではありません。ただし、このテンプレートの `bun run setup` と署名付き公開用ツールは現在Swiftで実装されており、セットアップはmacOSとXcode 27を要求します。Bunだけで署名・公開が完結する手順にはなっていません。

TypeScriptの編集、型チェック、パッケージ生成、ドキュメントのビルドは、Xcodeなしでも実行できます。移植可能な範囲の確認には `bun run check:authoring` を使い、現在の署名付き公開にはこのページの手順を使ってください。
