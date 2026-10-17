# 公式プラグイン配布リポジトリと作成用テンプレート

日付: 2026-10-17（日本時間）

状態: 2026-10-17、ユーザーがこの仕様を承認し、追加確認なしで実装・テスト・公開まで進めることを指示。実装中。

## 目的と範囲

利用者がInterceptorにURLを登録してサンプルを読み込み、ソースと権限を確認し、合成イベントで試行できる公式配布先を作る。同じリポジトリをテンプレートとして使い、自分のJavaScriptを配布できるようにする。

公式配布先は公開GitHubリポジトリ `qtmleap/Interceptor-Plugins`、既定ブランチは `main` とする。GitHubのテンプレート機能を有効にする。配布先はGitHub Pages、登録するURLは `https://qtmleap.github.io/Interceptor-Plugins/repository.json` とする。これらは作成予定の名前・URLであり、現時点で公開済みではない。

アプリのv1配布形式を維持し、アプリのコードやスキーマは変更しない。アプリ・実行基盤の基準は公開済みコミット `50307c2af38be2524f988e3d1d8a950973d63fd5`。現在の基盤は明示的な合成イベントの試行と結果表示までを提供する。実キャプチャへの自動フック、バックグラウンド実行、Webhook送達をサンプルの機能として案内しない。

## 構成の選択

独立した配布リポジトリを採用する。既存アプリの `examples/` のみを拡充する案より登録URLと利用者のFork先を分かりやすくでき、サーバーAPIを追加する案より既存の静的配布形式をそのまま使える。

```text
README.md                       英語の使い方と日本語版へのリンク
README.ja.md                    日本語の登録・試行・作成手順
LICENSE                         MIT、2026 QuantumLeap
repository-config.json          リポジトリUUID・名前・固定した実行基盤SHA
scripts/request-summary.js      編集するJavaScript
scripts/server-error-filter.js
manifests/request-summary.json  ソースと分けたv1 manifest
manifests/server-error-filter.json
fixtures/                       合成入力、設定、期待する出力
tools/                          生成処理、実行・配布検証、鍵の利用手順
.github/workflows/              PR検証と公式Pages配布
build/site/plugins/*.json       生成物、Git管理対象外
build/site/repository.json      生成物、Git管理対象外
.tools/interceptor/             固定SHAの公開アプリ取得先、Git管理対象外
```

各サンプルの `.js` とmanifestを組み合わせ、配布用の `{manifest, source}` JSONを生成する。対応するファイルが欠ける、余分なファイルがある、IDが重複する場合は失敗にする。JSONはUTF-8、キー順・改行を固定して生成し、同じ入力から同じパッケージバイト列を得る。sequence・発行日・有効期限・署名は一覧の `repository.json` にだけ含め、`plugins/*.json` の再現性には影響させない。

リポジトリUUIDは `90A213C0-9D3C-47F5-ABB8-C15C7472E2AD`。request-summaryは `76532D8C-608A-4EA3-AC16-755BABF2AB7E`、server-error-filterは `5B478646-4A70-4EF1-B04B-6CB63450E5A4`。公式版ではIDと登録URLを維持する。テンプレートから新しく配布する際は、リポジトリとサンプルのID、名前、URL、署名鍵を自分用に変更する。公式のowner/name以外で公式のID・URL・指紋を残した署名配布はCIで失敗にする。ソースや宣言の変更時はSemVerも更新する。

## 初期サンプル

### Request summary

`onRequest(event, config)` を定義する。`example.com` のGETリクエストを対象とし、`event.request.method`、`event.request.host`、`event.request.path` から要約を作る。合成入力の既定値では `GET example.com/synthetic` を含む1件の表示用アクションを返す。GET以外では空のアクションを返す。

### Server error filter

`onResponse(event, config)` を定義する。`example.com` のレスポンスを対象とし、`event.response.status` が500〜599のときだけ、ホストとステータスを含む1件の表示用アクションを返す。既定の503では1件、200と範囲外では0件になる。manifestにも500〜599を宣言するが、試行でmanifestの条件が自動適用されると仮定せず、JavaScript側でも判定する。

両方とも必要なmetadataだけを宣言し、headers・queryKeysは空、bodyは `none` とする。`endpointBindings` は `preview` だけにし、アクションの `endpointId` は `config.endpoints.preview` を使う。試行結果は表示のみで送信しない。READMEでは選択するRequest／Responseフックをサンプルごとに示す。

入力と設定はアプリの `SyntheticFixture.swift` と一致させる。previewのUUIDは `5E1D0C4A-0000-4000-8000-00000000A001`。期待値はJSONとして比較し、オブジェクトの表示順に依存しない。

## 生成と実行検証

固定SHAのアプリを取得して、`Packages/InterceptorAutomation` の既存publisherと `AutomationRuntime`、`AutomationCore` を再利用する。SwiftPMはGitリポジトリのサブディレクトリを直接URL依存にできないため、取得先を `.tools/interceptor` に固定し、検証用の小さなSwift Packageからローカルパス依存にする。QuickJSや署名実装はコピーしない。

publisherでmanifestと配布パッケージを検証し、一覧、SHA-256、size、署名を生成する。実行検証はアプリと同じQuickJSを呼び、宣言だけが正しくても出力が誤っていれば失敗にする。Nodeなど別のエンジンの結果をアプリ互換性の証拠にしない。

ローカルとCIの実行環境はmacOS 14以降、Swift 6以降とする。CIの初期runnerはGitHub-hosted `macos-15`。アプリのXcodeビルドやシミュレータは不要。実行時にアプリSHAとSwift・Xcodeのバージョンを証跡へ保存する。現在のAutomation packageは外部SwiftPM依存がなく、QuickJSも取得したSHA内に固定されている。将来外部依存を追加する場合は解決済みバージョンの固定を必須にする。runner更新後もその環境で全サンプルの結果を再検証し、別バージョンの過去のテストを流用しない。固定SHAの取得に失敗したら停止し、最新ブランチや別の配布物へ切り替えない。

## 署名と信頼

公式の配布一覧は既存publisherによるEd25519署名を必須にする。各パッケージのSHA-256は、配布する正確なバイト列について計算する。ハッシュと公開者の認証を区別し、初回に見た署名鍵をアプリが自動で信頼すると案内しない。

鍵はMac上で一度だけ、Git checkoutと配布ディレクトリの外に生成する。秘密鍵ファイルは0600。CIへはmainに制限した配布environmentの専用Secretで渡す。mainの配布ジョブだけがrunnerの一時ディレクトリへ復元し、終了時に削除する。手動実行も公式owner/nameと `refs/heads/main` の一致を必須にする。PR検証は秘密鍵や配布権限を使わず、未署名の一時一覧で検証する。公式配布で鍵がない場合は失敗し、未署名へフォールバックしない。週次更新に毎回の承認を要求する新しいフローは追加せず、組織の既存必須ルールがあれば従う。

公開鍵のSHA-256指紋をREADMEと納品時のチャットに掲載する。READMEと配布先が同じGitHub管理権限の影響を受ける点は隠さず、信頼済みの別チャネルで指紋を照合してからpinする手順を記す。アプリに鍵ローテーションの仕組みを追加することは今回の範囲に含めない。鍵の変更を自動追認せず、鍵を失った場合の再登録手順を文書化する。

漏えいが疑われる場合はqtmleapのリポジトリ管理者が配布workflowを止め、Secretを無効化し、配布を停止する。既にインストールされたものやpinされた鍵を遠隔失効できるとは案内しない。新しい鍵・UUID・URLによる移行と、各利用者による再登録・指紋確認が必要になる。告知先は既存のqleap.jp公式サイトとし、GitHubの案内と合わせて管理者が公表する手順を記す。これは事故時の運用手順であり、今回サイト改修や利用者へのメッセージ送信は行わない。

移行時に限り、管理者が公式リポジトリ内で設定・README・CIの予約値をレビュー付きで更新し、新しいUUID・指紋・配布パス（例: `recovery-20261017/repository.json`）へ切り替える。通常時のID・URL固定にはこの事故対応の例外がある。旧ID・指紋も公式予約値として残し、公式以外のテンプレート配布が新旧どちらの公式IDも流用できないようにする。既存URLから新URLへの自動転送は行わず、利用者は新URLを明示的に登録する。

テンプレートは自分のIDと鍵に設定してから署名配布する。ローカルの未署名出力ではアプリの未認証警告が出ることを説明する。公式リポジトリの秘密鍵はテンプレートに含まれない。

## 公開と更新

生成物だけをGitHub Pagesへ配布する。`repository.json` と秘密鍵をソースのGit履歴へ含めない。main更新・手動実行・週次の実行で新しい一覧を生成する。一覧の有効期間は既存publisherの30日を維持する。

sequenceはUnixミリ秒を使い、1〜2^53−1の範囲に収める。発行時刻と同じ時計から生成し、任意の将来値を指定する入力は用意しない。アプリの既存verifierによる発行時刻の未来上限（300秒）も公開検証に使う。配布処理全体を一つの固定 `concurrency` group、`cancel-in-progress: false` で直列化する。既存一覧を取得できる場合は新しいsequenceが上回ることを確認し、同値や時計巻き戻りでは配布を止める。初回404以外の取得失敗を、初回として黙って扱わない。配布直前にmainの先頭SHAを照合し、古いmainの成果物が後から出荷される場合も停止する。

古いmainのrunは成功扱いのskipにせず、非ゼロで終了する。新しいmainの配布runが完了したことを確認し、該当runがなければ管理者が手動実行する。処理中の別runや不明な配布結果を推測して自動で再送しない。

配布ジョブはmainのコードのみを実行し、Pages用environmentと必要な権限を使う。ForkのPRでは検証だけを行い、署名やPages配布は実行しない。GitHub Actionsの外部参照とアプリの取得先はコミットSHAで固定する。

公開後は登録URLを匿名HTTPSで読み戻し、リダイレクトなしの200、公式UUID、署名と指紋、期待するsequence、期限まで14日以上あることを確認する。全パッケージを実URLから取得し、size・SHA-256・manifestの一致を確認する。CDN反映中の不一致には上限付きの再試行を行い、解消しなければ公開確認失敗として扱う。

読み戻したsequenceは今回公開した値との完全一致を必須とし、古い一覧も新しい別runの一覧も今回の成功証跡にしない。再試行はHTTPSの読み戻しだけを行い、再生成・再署名・再公開は行わない。

GitHubの公開リポジトリでは、60日間活動がないとscheduleが無効になる。週次実行だけで永久に更新が保証されるとは案内せず、無効化時の再有効化・手動更新と期限切れからの復旧手順を記す。運用責任はqtmleapのリポジトリ管理者が持ち、週次のworkflow状態と一覧期限を確認する。GitHubからの失敗通知を補助にするが、無効化後にジョブが走らなければチェック自体も走らない点を明示する。外部cronサービスや新しい運用サーバー、自動監視が存在するとは扱わない。初回公開時には週次workflowが有効なことまで確認する。

## 検証と完了条件

1. サンプル生成を2回行い、パッケージがバイト単位で一致する。
2. アプリと同じvalidatorが両パッケージと一覧を受理する。
3. QuickJSでGET要約、GET以外、503、500、599、200、499、600の期待結果を確認する。各サンプルで正しいフックを使い、誤ったフックはエラーとなることを明示する。
4. パッケージを1バイト変更するとSHA-256検証が失敗し、一覧の改変は署名検証が失敗する。
5. PR検証とmain配布の権限・Secret利用が分離され、公式鍵がない配布は失敗する。
6. 英日READMEから登録、該当フックでの試行、ソース編集、パッケージ生成、自分用のID・署名への変更手順を追える。
7. ローカル検証と独立した実装レビューが完了し、必要なCIが成功する。
8. 実際に公開されたURLを匿名で読み戻し、上記の署名・期限・ハッシュ確認が成功する。

ソース準備、CI成功、Pagesへの配布完了、公開URLの検証完了は別々に記録する。未実施のアプリ画面での読み込み確認を、ツールの検証結果から実施済みと扱わない。将来のUI確認を行う場合も、OS・端末とキャプチャを記録する。

## 調査と根拠

- 現行アプリ: `docs/automation/publishing-repository.md`、`Packages/InterceptorAutomation/Sources/RepositoryPublisher/main.swift`、`AutomationCore/Index.swift`、`Interceptor/Automation/SyntheticFixture.swift` と `AutomationTemplate.swift`。
- 既存 `examples/plugin-repository/plugins/request-summary.json` のトップレベル `event.method` はアプリの合成入力と一致しない。新しいサンプルでは `event.request.method` を使い、実行結果をテストする。
- Claude Codeによる実ファイルの独立した実現性レビューが完了。SwiftPMのサブディレクトリ依存、入力形式、試行の条件、署名・sequence・期限の指摘をこの仕様へ反映した。レビュー証跡は実装担当者が保持し、公開リポジトリには秘密鍵・ローカル作業ログを含めない。
- LocalGPTはブラウザ未接続のため、この件の計画レビューは未実施。接続の迂回や、ファイルを貼り付けた代替レビューは行っていない。
- [GitHub Pagesのカスタムworkflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [scheduleの無効化と再有効化](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)

実装時の検証結果: 当初のmacos-15 runnerでは既定のSwift 6.1が固定ライブラリのactor-isolationコードを拒否した。実際のCIは公式のxcode-27 hosted imageとXcode 27.0.0（Swift 6.4）を明示的に使用し、ネイティブ検証と揃える。古いコンパイラは取得前に拒否する。上流ソースや並行処理チェック、packageのmacOS 14 deployment targetは変更しない。
