# SplatNet 3 Token Export

Nintendo Switch AppでSplatNet3を開いたときに発行されるBullet Tokenを、MacでJSONを取得するためのファイルへ書き出します。このPlugin単体で利用できます。

## 使い方

1. パッケージをインポートして有効にし、このPluginの保存先としてiCloud Drive内の`SplatNet3`フォルダを選択します。Salmon Run用のフォルダ許可とは別です。
2. Nintendo Switch AppでSplatNet3を開き、新しいTokenを取得します。
3. Interceptorを開いてファイルを書き出し、MacへのiCloud同期を待ちます。`SplatNet3/auth.json`に次の項目が保存されます。

| 項目 | 内容 |
| --- | --- |
| `bulletToken` | 発行されたBullet Token |
| `webViewVersion` | 取得時の`x-web-view-ver` |
| `language` | 応答の`lang`。利用できない場合は要求の`accept-language` |
| `userAgent` | 取得できた場合のみ保存するUser-Agent |

ファイルには平文の認証情報が含まれます。公開・共有・Gitへのコミットをしないでください。

新しく発行された有効なTokenと必要な項目が揃うと、同じパスの保存データを更新します。Mac側はこのファイルを読み取り専用で扱ってください。手動で置いた同名ファイルや編集済みファイルは、ホストの上書き保護により競合します。

`createFile`の完了はInterceptor内への保存完了です。iCloudへの書き出しと同期の完了は別で、保存先の許可とInterceptorの前面実行が必要です。失敗した書き出しは本体がデータを保持して再試行します。

## Macから1件取得する例

以下を`fetch-once.ts`として保存し、Bunで実行できます。`request.json`には取得したいGraphQL要求のJSONを用意します。Tokenだけではクエリのハッシュやvariablesは分からないため、使用中のSplatNet3の要求に対応する値が必要です。

```ts
const [authPath, requestPath, outputPath] = Bun.argv.slice(2)
if (!authPath || !requestPath || !outputPath) {
  throw new Error('Usage: bun fetch-once.ts AUTH_JSON REQUEST_JSON OUTPUT_JSON')
}
const auth = await Bun.file(authPath).json()
const response = await fetch('https://api.lp1.av5ja.srv.nintendo.net/api/graphql', {
  method: 'POST',
  headers: {
    authorization: 'Bearer ' + auth.bulletToken,
    'x-web-view-ver': auth.webViewVersion,
    'accept-language': auth.language,
    'content-type': 'application/json',
    'x-requested-with': 'XMLHttpRequest',
    ...(auth.userAgent ? { 'user-agent': auth.userAgent } : {}),
  },
  body: await Bun.file(requestPath).text(),
})
if (!response.ok) throw new Error('SplatNet3 HTTP ' + response.status)
await Bun.write(outputPath, await response.text())
```

```sh
bun fetch-once.ts /path/to/SplatNet3/auth.json request.json result.json
```

401/403などの認証失敗時は、SplatNet3を開き直して新しいTokenを取得し、ファイルの更新・同期を確認してください。このPluginはTokenの有効期限を監視せず、失効したファイルも自動削除しません。不要になった認証ファイルは削除してください。

## 動作と検証

`POST /api/bullet_tokens`のHTTP 201応答だけを`response.onLeave`で処理します。Token・Web版・言語は空白だけでない文字列で、ASCII制御文字を含まないものを使用します。未知のWeb版も保存します。利用できないTokenは保存せず、必要な版・言語が欠ける場合は`missing-context`で停止します。保存エラーも停止します。CookieやGame Web Token、診断結果への認証情報の追加、Pluginからの通信はありません。

```sh
bun run build
PYTHONPATH=tests python3 -m unittest -v test_splatnet3_token_export
```

生成物は`build/scripts/splatnet3-token-export/`、`build/manifests/splatnet3-token-export.json`、`build/dev/plugins/splatnet3-token-export.json`です。テストは生成済みPluginと共有QuickJSを実行し、保存先・内容・失敗時の動作を確認します。実際のNintendo通信・M3での動作・iCloud配送を確認するテストとは区別します。
