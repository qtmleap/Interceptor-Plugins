# SplatNet 3 Salmon Run

Nintendo Switch Appでスプラトゥーン3を開いた際の
`POST /api/bullet_tokens` 応答を `response.onLeave` で読み取ります。
取得したBulletTokenで、JS内の `fetch` からサーモンランの履歴と各リザルトを取得します。
送信先・メソッド・ヘッダー・本文は `POST.ts` 内で定義しています。

- `settings.maxResults`: 1回に取得する詳細の上限。既定値50、範囲1〜50。
- 重複したリザルトIDは1回だけ取得します。401/403では再試行せず停止します。
- 404と削除済みの詳細は読み飛ばします。要求した結果IDとの不一致やプレイヤーIDの欠落では停止します。プレイヤーIDは結果ごとに変わるため、結果間では比較しません。
- 履歴の応答本文と、検証に成功した各詳細の応答本文を、元の文字列のまま `Interceptor.createFile` で iCloud Drive（`Interceptor.Storage.iCloudDrive`）へ保存します（`write.files: true`）。
  履歴は `Salmon Run/history.json`、詳細は `Salmon Run/details/<リザルトIDのSHA-256（16進64文字）>.json` です。リザルトIDは長く `/` を含み得るため、ファイル名にはIDそのものを使いません。トークンやラッパーは保存しません。
  Promiseは本体内の保存が完了すると解決します。Interceptorを開くと、許可したiCloud Drive内のフォルダへ書き出します。iCloudへのアップロードはOSが行います。
  初回にiCloud Drive内の「Salmon Run」を選択して許可します。JSのパスは上記のままで、本体が先頭の`Salmon Run/`を一度だけ取り除いて、選択したフォルダへ保存します。
  本体内への保存に失敗した時点で取得を停止し、それまでの保存は残ります。iCloudへの書き出しに失敗した場合は、本体内のデータを保持して再試行します。
- 既存の診断結果には取得済みID・未取得ID・残数だけを返します。
  これはHTTP送信ではなく、本体での保存や通知も追加しません。

詳細ファイル名のSHA-256は固定版の `js-sha256` をビルド時に同梱して計算します（独自実装はありません）。

対応するクエリ定義は `4.0.0-091d4283` と `10.0.0-d15503c4` です。
取得時の `x-web-view-ver` が完全一致しない場合（未知の版を含む）は、推測せず停止します。定義の出典は
[splatnet3-queries.json](../../docs/development/splatnet3-queries.json) を参照してください。
旧保存APIを使ったM3検証では、インストール済みPluginがBulletToken応答（`x-web-view-ver: 10.0.0-d15503c4`）から自動実行され、
履歴JSONと詳細50件を保存できました。今回の`createFile`によるiCloud Driveへの保存は、別途M3で確認します。
`4.0.0-091d4283` の実サーバーでの受理も未検証です。

## ビルドと検証

```sh
bun run build
tools/build-runtime.sh
python3 -m unittest discover -s tests -p 'test_splatnet3_*.py' -v
SPLATNET3_TEST_SOURCE="$PWD/build/scripts/splatnet3-salmon/hooks/api.lp1.av5ja.srv.nintendo.net/api/bullet_tokens/POST.js" \
  python3 -m unittest discover -s tests -p test_splatnet3_hook.py -v
```

生成物は `build/scripts/splatnet3-salmon/`、
`build/manifests/splatnet3-salmon.json`、
`build/dev/plugins/splatnet3-salmon.json` です。

実行には、標準の `fetch` と非同期 `response.onLeave` を扱えるInterceptor本体が必要です。
対応するQuickJS実装は、対になるInterceptor側の変更で追加しています。
共有するCブリッジをRustシミュレーターでも使い、生成済みPluginを検証します。
Nintendoの実サーバーでの取得確認とは区別してください。
