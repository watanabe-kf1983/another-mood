# Pipeline

ユーザの定義・コンテンツから最終的なドキュメントを生成するパイプライン。

## Internal Design

### ステージ構成

> **[W4 dup]** ↔ pipeline/stages.py の bind 引数と STAGE_FACTORIES/TAP_STAGE_FACTORIES コメント (a, 表はコードの写し)、docs/reference/cli.md:87-92 (b)。跨るモジュールの構造。案: 残す

| ステージ | User Input | Upstream | Output |
|---|---|---|---|
| inspect_schema | schema_file | — | inspect_schema/ |
| normalize_contents | contents_dir | inspect_schema/ | normalize_contents/ |
| derive_queries | views_dir | inspect_schema/ | derive_queries/ |
| compose | — | normalize_contents/, derive_queries/, inspect_schema/ | compose/ |
| generate | templates_dir, reports_file | compose/ | generate/ |
| reconcile | — | generate/ | reconcile/ |
| site | — | reconcile/ | prepare_site/, hugo_build/ |
| publish | — | hugo_build/ | out_dir（reconcile/ の内容）, site_dir（hugo_build/ の内容） |

Output は作業ディレクトリ（`Workspace.root`）直下のコンポーネント名ディレクトリ。`mood tap` は compose までを共有し、tap（compose/ → tap/）と publish（tap_dir）で終わる（`pipeline/stages.py` の `TAP_STAGE_FACTORIES`）。

dev モードでは User Input / Upstream の変更を Watch してステージを自動再実行する（`pipeline/base.py` 参照）。build モードでは依存順に直列実行する。Upstream は前段ステージの Output であり、`BuildReport`（エラー伝播）の収集対象。

### 背景: Watch ライブラリは watchdog を採用

> **[W4 → appendix]**

[watchdog](https://github.com/gorakhargosh/watchdog) を採用。過去に [watchfiles](https://github.com/samuelcolvin/watchfiles) を採用していた (PR #41) が、watchfiles は WSL を検出すると WSL1/WSL2 を区別せず強制 polling に切り替える挙動があり (issue #187、2022)、WSL2 環境で polling モードの event 取りこぼしが発生して watch が停止する問題があった (実測で `mood watch` 稼働中に concurrent `mood build` を当てると 10 回中 7 回最終状態が "failed" で固定)。

watchdog は Linux (WSL2 を含む) で inotify を使い、明示的に指定しない限り polling に落ちないため、WSL1 のような特殊ケースを考慮しなくてよい。OS ネイティブの event 通知機構を使う点は両ライブラリ共通だが、WSL の自動 polling 判定の挙動が異なる。

#### watchdog 利用上の注意: 変更系 event のみに subscribe

> **[W4 → code]** 削除 (watcher.py の `_Handler` コメントに同じ申し送りあり。watchfiles への言及は上の節と一緒に appendix へ)

`Watcher` クラス (`pipeline/adapters/watcher.py`) の event handler は `on_created / on_modified / on_deleted / on_moved` のみオーバーライドし、`on_opened / on_closed` は意図的に無視する。

inotify は `IN_OPEN / IN_CLOSE_NOWRITE` などの読み取り系 event も emit し、watchdog のデフォルト (`on_any_event`) はこれらも拾ってしまう。カスケード watcher の handler は upstream を `transfer_tree` (copytree) で読み込むため、**自身の読み込みが watch 対象上に open/close event を発生させ、watcher が自己トリガーし続ける** 挙動を引き起こす (watchfiles は library レベルで読み取り系を filter するため同じ問題は出ない)。変更系 event に絞ることで、cascade が自然に終息する。
