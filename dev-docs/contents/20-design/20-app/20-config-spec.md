# 設定システム仕様

## External Design

### 設定の管轄範囲

> **[W4 dup]** ↔ config.py module docstring / vars コメント / with_injected_vars (a)、cli.md:34,253 (b) — 部分。契約+理由。案: 残す (design にしかない理由が主)

設定システムが扱うのは**起動時に実行者が差し出したもの**で、二種類ある:

- **起動パラメータ** — どう実行し、どこへ出すか: `project_dir` / `out_dir` / `site_dir` / `tap_dir` / `tmp_dir` / `host` / `port`
- **注入値 `vars`** — 実行者がテンプレートに届けたい荷物。設定システムは運ぶだけで中身を読まない（`verify` も `resolved_for_*` も触らない）。荷物を設定に同居させるのは、run に至るどの経路も既に config を一つ運んでいるため

ソースレイアウト（`definition/schema.yaml` 等のパス群）は設定ではなく sbdb フォーマット世代が定めるプロジェクト構造であり、`resolve_layout`（`layout.py`）が導出する。個別に位置を上書きする手段は持たない — フォーマット世代を名乗りながらファイル位置を動かせるのは、宣言と矛盾するため。

### 設定の読み込み優先順位

> **[W4 dup]** ↔ cli.md:272,295-304 (b)、config.py:32,46-49 (a) — 部分。約束。案: 削除→docs (「設定ファイル (未実装)」の一行は Proposals へ)

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル（未実装。[Proposals](#proposals) 参照）
3. 環境変数
4. CLI 引数

### 環境変数の綴り

> **[W4 dup]** ↔ cli.md:268-270,282-291 (b, 例まで同じ)、config.py:18-20 (a) — 完全。約束+理由。案: 規則は削除→docs。封筒を剥がす理由 (Java -D) と「復号器の限界」は意図の一文として残す

プレフィックスは `MOOD_`。設定キーを大文字化して前置するだけで、`out_dir` → `MOOD_OUT_DIR`。実装は pydantic-settings の `env_prefix="MOOD_"`。

`vars` だけは綴りが違い、`MOOD_VARS_<NAME>` から `MOOD_VARS_` を剥がして小文字化したものがキーになる（`MOOD_VARS_GIT_SHA` → `vars["git_sha"]`）。**封筒はストアのキーに入らない** — プレフィックスは共有名前空間（プロセス環境）で自分宛ての値を仕分けるチャネル固有の作法であり（Java の `-D` に相当）、ストア内では全キーに共通で情報を持たないため剥がす。残る `_` は分割子ではなく名前の一部で、`MOOD_VARS_CI_RUN_URL` は `vars["ci_run_url"]` になる。

**env で書けるのは vars 直下一段のみ**。深い階層キー（`vars.ci.run_id`）は CLI / MCP からドット入りキーとして渡せば成立する（ストアはフラットな文字列キーで、ドットはただの文字）。制限は env チャネルの復号器の限界であって、ストアと照会には制限がない。

## 背景: preflight の順序

> **[W4 dup]** ↔ 60-sbdb-manifest.md ゲートの実装「欠落の検出は read_manifest が持ち…」(c, 同じ論証)、layout.py:24-25、command.py build の呼び出し順 (a) — 完全。不変条件 (順序)+理由。案: ここを正本、sbdb-manifest 側の箇条をポインタ化

ソースパスの存在検証は `ProjectConfig.verify` ではなくレイアウト解決の後段で行い、失敗は `UserError` 系の precondition 例外として CLI / MCP 境界で出す（build-report には積まない）。パスが絶対であることの検査と `project_dir` の検証（`namespace_root` 配下 + 存在）だけが config 側に残る — manifest を読む前提条件のため。

preflight の順序: `project_dir` 検証 → manifest 読込 → 版ゲート → レイアウト解決 → ソース存在検証。レイアウト解決を manifest 読込より後に置くのは、`resolve_layout` が将来 `sbdb_version` で版ディスパッチする拡張点であり、非対応版プロジェクトには「Source paths not found」より先に「非対応版」を出すべきため（詳細は [60-sbdb-manifest](node:/prose/20-design/20-app/60-sbdb-manifest)）。

## Proposals

### 設定ファイル (G2)

- ファイル名: `another-mood.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON
