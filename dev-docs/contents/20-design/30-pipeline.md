# Pipeline

ユーザの定義・コンテンツから最終的なドキュメントを生成するパイプライン。

## Internal Design

### ステージ構成

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

Output は作業ディレクトリ（`Workspace.root`）直下のコンポーネント名ディレクトリ。`mood tap` は compose までを共有し、tap（compose/ → tap/）で終わる（`pipeline/stages.py` の `TAP_STAGE_FACTORIES`）。`mood tap --schema` は derive_queries までを共有し、tap_schema（derive_queries/ → tap_schema/）で終わる（`TAP_SCHEMA_STAGE_FACTORIES`）。どちらも publish は持たず、command 層が文書を読み取って返す。

dev モードでは User Input / Upstream の変更を Watch してステージを自動再実行する（`pipeline/base.py` 参照）。build モードでは依存順に直列実行する。Upstream は前段ステージの Output であり、`BuildReport`（エラー伝播）の収集対象。

### Watch ライブラリは watchdog を採用

[watchdog](https://github.com/gorakhargosh/watchdog) を採用。以前の watchfiles は WSL を検出すると WSL2 でも強制 polling に切り替わり、event の取りこぼしで watch が停止したため（[背景](../90-appendix/20-design/30-pipeline.md#watch-ライブラリは-watchdog-を採用)）。
