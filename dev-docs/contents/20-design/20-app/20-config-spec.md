# 設定システム仕様

## External Design

### 設定の管轄範囲

設定システムが扱うのは**起動時に実行者が差し出したもの**で、二種類ある:

- **起動パラメータ** — どう実行し、どこへ出すか: `project_dir` / `out_dir` / `site_dir` / `tmp_dir` / `host` / `port`
- **注入値 `vars`** — 実行者がテンプレートに届けたい荷物。設定システムは運ぶだけで中身を読まない（`verify` も `resolved_for_*` も触らない）。荷物を設定に同居させるのは、run に至るどの経路も既に config を一つ運んでいるため

ソースレイアウト（`definition/schema.yaml` 等のパス群）は設定ではなく sbdb フォーマット世代が定めるプロジェクト構造であり、`resolve_layout`（`layout.py`）が導出する。個別に位置を上書きする手段は持たない — フォーマット世代を名乗りながらファイル位置を動かせるのは、宣言と矛盾するため。

### 設定の読み込み優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル（未実装 — [G2](node:/tasks/G/tasks/G2)）
3. 環境変数
4. CLI 引数

### 環境変数の綴り

プレフィックスは `MOOD_`。設定キーを大文字化して前置するだけで、`out_dir` → `MOOD_OUT_DIR`。実装は pydantic-settings の `env_prefix="MOOD_"`。

`vars` だけは綴りが違い、`MOOD_VARS_<NAME>` から `MOOD_VARS_` を剥がして小文字化したものがキーになる（`MOOD_VARS_GIT_SHA` → `vars["git_sha"]`）。**封筒はストアのキーに入らない** — プレフィックスは共有名前空間（プロセス環境）で自分宛ての値を仕分けるチャネル固有の作法であり（Java の `-D` に相当）、ストア内では全キーに共通で情報を持たないため剥がす。残る `_` は分割子ではなく名前の一部で、`MOOD_VARS_CI_RUN_URL` は `vars["ci_run_url"]` になる。

**env で書けるのは vars 直下一段のみ**。深い階層キー（`vars.ci.run_id`）は CLI / MCP からドット入りキーとして渡せば成立する（ストアはフラットな文字列キーで、ドットはただの文字）。制限は env チャネルの復号器の限界であって、ストアと照会には制限がない。

## 背景: preflight の順序

ソースパスの存在検証は `ProjectConfig.verify` ではなくレイアウト解決の後段で行い、失敗は `UserError` 系の precondition 例外として CLI / MCP 境界で出す（build-report には積まない）。パスが絶対であることの検査と `project_dir` の検証（`namespace_root` 配下 + 存在）だけが config 側に残る — manifest を読む前提条件のため。

あるべき preflight 順序: `project_dir` 検証 → manifest 読込（V1）→ 版ゲート（V4）→ レイアウト解決 → ソース存在検証。レイアウト解決を manifest 読込より後に置くのは、`resolve_layout` が将来 `sbdb_version` で版ディスパッチする拡張点であり、非対応版プロジェクトには「Source paths not found」より先に「非対応版」を出すべきため（詳細は [60-sbdb-manifest](node:/prose/20-design/20-app/60-sbdb-manifest)）。

## Proposals

### 設定ファイル (G2)

- ファイル名: `another-mood.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON

### vars の CLI / MCP チャネル (P14 #6)

env チャネル（`MOOD_VARS_*`）は実装済み。残るのは実行者が直接渡す二つ:

- CLI: `--var aaa_bbb=x`（繰り返し可）
- MCP: `build` 引数 `vars`（mapping）

**合流は構築後に足す**: `config.model_copy(update={"vars": {**config.vars, **cli_vars}})`。`ProjectConfig(vars=...)` と construct 時の引数で渡してはいけない — default はマージではなく置換なので、`default_factory` が読んだ env の注入が丸ごと落ちる（実測）。設計が求める優先順位（衝突は init が env に勝つ）は、この一行の綴りにそのまま出る。
