# Pipeline

ユーザの定義・コンテンツから最終的なドキュメントを生成するパイプライン。

| ステージ | User Input | Upstream | Output |
|---|---|---|---|
| inspect_schema | schema_file | — | inspect_schemas_dir |
| normalize_contents | contents_dir | inspect_schemas_dir | normalize_contents_dir |
| derive_queries | queries_dir | inspect_schemas_dir | derive_queries_dir |
| compose | — | normalize_contents_dir, derive_queries_dir | compose_dir |
| generate | templates_dir | compose_dir | generate_dir |
| reconcile | — | generate_dir | reconcile_dir |
| render | — | reconcile_dir | render_dir |

dev モードでは User Input / Upstream の変更を Watch してステージを自動再実行する（`pipeline/base.py` 参照）。build モードでは依存順に直列実行する。Upstream は前段ステージの Output であり、`BuildReport`（エラー伝播）の収集対象。

## 背景: Watch ライブラリは watchdog を採用

[watchdog](https://github.com/gorakhargosh/watchdog) を採用。過去に [watchfiles](https://github.com/samuelcolvin/watchfiles) を採用していた (PR #41) が、watchfiles は WSL を検出すると WSL1/WSL2 を区別せず強制 polling に切り替える挙動があり (issue #187、2022)、WSL2 環境で polling モードの event 取りこぼしが発生して watch が停止する問題があった (実測で `mood watch` 稼働中に concurrent `mood build` を当てると 10 回中 7 回最終状態が "failed" で固定)。

watchdog は Linux (WSL2 を含む) で inotify を使い、明示的に指定しない限り polling に落ちないため、WSL1 のような特殊ケースを考慮しなくてよい。OS ネイティブの event 通知機構を使う点は両ライブラリ共通だが、WSL の自動 polling 判定の挙動が異なる。

### watchdog 利用上の注意: 変更系 event のみに subscribe

`Watcher` クラス (`pipeline/adapters/watcher.py`) は `on_created / on_modified / on_deleted / on_moved` のみオーバーライドし、`on_opened / on_closed` は意図的に無視する。

inotify は `IN_OPEN / IN_CLOSE_NOWRITE` などの読み取り系 event も emit し、watchdog のデフォルト (`on_any_event`) はこれらも拾ってしまう。カスケード watcher の handler は upstream を `shutil.copytree` で読み込むため、**自身の読み込みが watch 対象上に open/close event を発生させ、watcher が自己トリガーし続ける** 挙動を引き起こす (watchfiles は library レベルで読み取り系を filter するため同じ問題は出ない)。変更系 event に絞ることで、cascade が自然に終息する。
