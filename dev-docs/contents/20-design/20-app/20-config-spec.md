# 設定システム仕様

## External Design

### 設定の管轄範囲

設定システムが扱うのは**起動パラメータ**（どう実行し、どこへ出すか: `project_dir` / `out_dir` / `render_dir` / `tmp_dir` / `host` / `port`）のみ。

ソースレイアウト（`definition/schema.yaml` 等のパス群）は設定ではなく sbdb フォーマット世代が定めるプロジェクト構造であり、`resolve_layout`（`layout.py`）が導出する。レイアウトの `RB_*` 個別オーバーライドは廃止済み（[G10](node:/tasks/G/tasks/G10) — フォーマット世代を名乗りながらファイル位置を動かせるのは宣言と矛盾するため）。

### 設定の読み込み優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル（未実装 — [G2](node:/tasks/G/tasks/G2)）
3. 環境変数
4. CLI 引数

## 背景: preflight の順序

ソースパスの存在検証は `ProjectConfig.verify` ではなくレイアウト解決の後段で行い、失敗は `UserError` 系の precondition 例外として CLI / MCP 境界で出す（build-report には積まない）。`project_dir` の検証（CWD 配下 + 存在）だけが config 側に残る — manifest を読む前提条件のため。

あるべき preflight 順序: `project_dir` 検証 → manifest 読込（V1）→ 版ゲート（V4）→ レイアウト解決 → ソース存在検証。レイアウト解決を manifest 読込より後に置くのは、`resolve_layout` が将来 `sbdb_version` で版ディスパッチする拡張点であり、非対応版プロジェクトには「Source paths not found」より先に「非対応版」を出すべきため（詳細は [60-sbdb-manifest](node:/prose/20-design/20-app/60-sbdb-manifest)）。

## Proposals

### 設定ファイル (G2)

- ファイル名: `another-mood.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON
- スコープ注意: ソースレイアウトは設定項目にしない（G10 で設定システムの管轄外と決定 — 「設定の管轄範囲」参照）
