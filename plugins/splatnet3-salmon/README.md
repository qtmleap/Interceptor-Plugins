# SplatNet 3 Salmon Run

Nintendo Switch Appでスプラトゥーン3を開いた際の
`POST /api/bullet_tokens` 応答を `response.onLeave` で読み取ります。
取得したBulletTokenで、JS内の `fetch` からサーモンランの履歴と各リザルトを取得します。
送信先・メソッド・ヘッダー・本文は `POST.ts` 内で定義しています。

- `settings.maxResults`: 1回に取得する詳細の上限。既定値50、範囲1〜50。
- 重複したリザルトIDは1回だけ取得します。401/403では再試行せず停止します。
- 404と削除済みの詳細は読み飛ばします。IDやプレイヤーの不一致では停止します。
- 結果本文はJS実行中に取得・検証します。外部送信と永続保存はまだ行いません。
- 既存の診断結果には取得済みID・未取得ID・残数だけを返します。
  これはHTTP送信ではなく、本体での保存や通知も追加しません。

対応するクエリ定義は `4.0.0-091d4283` と `10.0.0-d15503c4` です。
取得時の `x-web-view-ver` が完全一致しない場合（未知の版を含む）は、推測せず停止します。定義の出典は
[splatnet3-queries.json](../../docs/development/splatnet3-queries.json) を参照してください。
2026-10-23、実機で捕捉したBulletToken応答（`x-web-view-ver: 10.0.0-d15503c4`）を生成済みPluginへ入力し、
InterceptorのQuickJS・標準 `fetch`・実トランスポートを通して、Nintendoの履歴APIのHTTP 200と空の履歴を確認しました。
詳細取得は履歴0件のため未検証です。インストール済みPluginがキャプチャから自動実行される経路は、この検証には含みません。
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
