# Pipeline

ユーザの定義・コンテンツから最終的なドキュメントを生成するパイプライン。

## ステージ構成

| ステージ | User Input | Upstream | Output |
|---|---|---|---|
| inspect_schema | schema_file | — | inspect_schema/ |
| normalize_contents | contents_dir | inspect_schema/ | normalize_contents/ |
| derive_queries | views_dir | inspect_schema/ | derive_queries/ |
| compose | — | normalize_contents/, derive_queries/ | compose/ |
| generate | templates_dir, reports_file | compose/ | generate/ |
| reconcile | — | generate/ | reconcile/ |
| site | — | reconcile/ | prepare_site/, hugo_build/ |
| publish | — | hugo_build/ | out_dir（reconcile/ の内容）, site_dir（hugo_build/ の内容） |
| tap | — | compose/ | tap/ |
| tap_schema | — | derive_queries/ | tap_schema/ |

Output は作業ディレクトリ（`Workspace.root`）直下のコンポーネント名ディレクトリ。site ステージは prepare_site と hugo_build の二つのコンポーネントを走らせるので出力も二つ。

publish は reconcile/ も写すが、監視するのは末尾の hugo_build/ だけ。それが完了した時点で前段はすべて落ち着いているため（`pipeline/stages.py` の `publish_stage`）。

normalize_contents は schema_file も読むが監視しない。スキーマの変更は inspect_schema/ の更新として届く（[データカタログ](30-communication/20-data-catalog.md)）。

`mood tap` と `mood tap --schema` は途中まで同じステージ列を共有し、末尾だけが違う（`pipeline/stages.py` の `TAP_STAGE_FACTORIES` / `TAP_SCHEMA_STAGE_FACTORIES`）:

- `mood tap` — compose まで共有し、tap（compose/ → tap/）で終わる
- `mood tap --schema` — derive_queries まで共有し、tap_schema（derive_queries/ → tap_schema/）で終わる

どちらも publish は持たず、command 層が文書を読み取って返す。

watch では User Input / Upstream の変更を監視してステージを自動再実行する（`pipeline/base.py` 参照）。build では依存順に直列実行する。Upstream は前段ステージの Output であり、`BuildReport`（エラー伝播）の収集対象。

## Watch ライブラリは watchdog を採用

[watchdog](https://github.com/gorakhargosh/watchdog) を採用。以前の watchfiles は WSL を検出すると WSL2 でも強制 polling に切り替わり、event の取りこぼしで watch が停止したため。
