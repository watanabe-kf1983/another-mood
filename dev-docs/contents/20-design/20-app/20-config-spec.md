# 設定システム仕様

## External Design

### 設定の読み込み優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル（未実装 — [G2](node:/tasks/G/tasks/G2)）
3. 環境変数
4. CLI 引数

## Proposals

### 設定ファイル (G2)

- ファイル名: `another-mood.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON
- スコープ注意: ソースレイアウトは設定項目にしない（[G10](#ソースレイアウトの分離-g10) で設定システムの管轄外と決定）

### ソースレイアウトの分離 (G10)

`ProjectConfig` からソースレイアウト 5 パス（`schema_file` / `reports_file` / `contents_dir` / `queries_dir` / `templates_dir`）を除去し、設定システムの管轄外にする。

- **レイアウトの導出**: `resolve_layout(project_dir) -> SourceLayout`（名称仮）で導出し、`Workspace` に載せて stages はそちらを読む。現時点では定数関数（v1 レイアウトのハードコード）で良い。将来 manifest（`sbdb_version`）を引数に足して版ディスパッチする拡張点として置く
- **`RB_*` レイアウトオーバーライドは完全廃止**: `RB_SCHEMA_FILE` / `RB_REPORTS_FILE` / `RB_CONTENTS_DIR` / `RB_QUERIES_DIR` / `RB_TEMPLATES_DIR` を削除し、docs/reference/cli.md の該当行も落とす。起動パラメータ系（`RB_OUT_DIR` / `RB_RENDER_DIR` / `RB_TMP_DIR` / `RB_HOST` / `RB_PORT`）は存続。内部利用は env 経由・`ProjectConfig` コンストラクタ経由ともゼロを確認済み（2026-07-22）
- **存在検証の再配置**: `project_dir` の検証（CWD 配下 + 存在）は `ProjectConfig.verify` に残す（manifest を読む前提条件のため）。ソースパス群の存在検証はレイアウト解決の後段へ移し、失敗は `UserError` 系の precondition 例外として CLI / MCP 境界で出す（build-report には積まない）

#### 背景: レイアウトはフォーマット仕様であって設定ではない

`definition/schema.yaml` 等のパス群は sbdb フォーマット世代が定めるプロジェクト構造であり、ユーザが起動時に選ぶものではない。V1（sbdb.yaml マニフェスト読込, PR #344）のレビューで依存逆転を診断した: 現行は `ProjectConfig` がレイアウトを固定し存在検証まで済ませた**後**に manifest を読むため、将来の非対応版プロジェクトを開いたとき「非対応版です」より先に「Source paths not found」が出て、版ゲートの fail-fast を横取りする。preflight 例外が `ConfigValidationError` / `ManifestError` の二系統に割れているのも同じ混在の症状。

あるべき preflight 順序: `project_dir` 検証 → manifest 読込 →（版ゲート: V4）→ レイアウト解決 → ソース存在検証。G10 はこの順序の受け皿を manifest 抜きで先に作る **V1 の前提タスク**（V1 は G10 マージ後に rebase し、manifest 読込をこの並びに差し込む）。
