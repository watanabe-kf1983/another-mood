# 設定システム仕様

## External Design

### 設定の管轄範囲

設定システムが扱うのは**起動パラメータ**（どう実行し、どこへ出すか: `project_dir` / `out_dir` / `site_dir` / `tmp_dir` / `host` / `port`）のみ。

ソースレイアウト（`definition/schema.yaml` 等のパス群）は設定ではなく sbdb フォーマット世代が定めるプロジェクト構造であり、`resolve_layout`（`layout.py`）が導出する。レイアウトの `RB_*` 個別オーバーライドは廃止済み（[G10](node:/tasks/G/tasks/G10) — フォーマット世代を名乗りながらファイル位置を動かせるのは宣言と矛盾するため）。

### 設定の読み込み優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル（未実装 — [G2](node:/tasks/G/tasks/G2)）
3. 環境変数
4. CLI 引数

## 背景: preflight の順序

ソースパスの存在検証は `ProjectConfig.verify` ではなくレイアウト解決の後段で行い、失敗は `UserError` 系の precondition 例外として CLI / MCP 境界で出す（build-report には積まない）。パスが絶対であることの検査と `project_dir` の検証（`namespace_root` 配下 + 存在）だけが config 側に残る — manifest を読む前提条件のため。

あるべき preflight 順序: `project_dir` 検証 → manifest 読込（V1）→ 版ゲート（V4）→ レイアウト解決 → ソース存在検証。レイアウト解決を manifest 読込より後に置くのは、`resolve_layout` が将来 `sbdb_version` で版ディスパッチする拡張点であり、非対応版プロジェクトには「Source paths not found」より先に「非対応版」を出すべきため（詳細は [60-sbdb-manifest](node:/prose/20-design/20-app/60-sbdb-manifest)）。

## Proposals

### 設定ファイル (G2)

- ファイル名: `another-mood.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON
- スコープ注意: ソースレイアウトは設定項目にしない（G10 で設定システムの管轄外と決定 — 「設定の管轄範囲」参照）

### 環境変数プレフィックス改名 (G14)

`RB_*` → `MOOD__*`。`RB` は旧名 reqs-builder の遺物で、由来不明の二文字を利用者の CI 設定ファイルに焼き付け続けないため、運用が広がる前に改名する。

**綴りは `MOOD_` でなく `MOOD__`（二連）を採る。** 環境変数名を「階層アドレスの `__` 結合エンコード」として読む一行規則に統一するため:

- `__`（二連）= 階層の区切り。`MOOD__OUT_DIR` = `[MOOD][OUT_DIR]`
- `_`（単独）= snake_case の語区切り（字義どおりの文字）

この規則は P14 の vars 注入（`MOOD__VARS__AAA_BBB` = `[MOOD][VARS][AAA_BBB]`）と同一で、pydantic-settings の `env_prefix="MOOD__"` + `env_nested_delimiter="__"` がそのまま実装になる。先例は ASP.NET Core の設定規約（`Logging__LogLevel__Default`）。

- **ツール破壊**（cli.md 記載の利用者向け契約）— 次リリースは 0.2.0。sbdb_version は不変（フォーマットに触れない）
- 旧綴りのエイリアスは残さない（現時点で外部利用者は事実上不在）
- PR 義務: cli.md への非互換注記一行、`Release-Highlight: breaking` トレーラー、highlight セクション
- **G14 → P14 の順で着手する**。P14 が確定させる env 綴りはこのプレフィックスの上に立つ

### ビルド時情報の供給機構 (P14 の config 側)

テンプレート照会関数 `build_info`（[30-template-spec.md](../70-generator/30-template-spec.md) の Proposals 参照）へ渡す利用者注入値 `vars.*` を、config 層で受ける。

- `ProjectConfig` に `vars: dict[str, str]` フィールドを追加。供給は三チャネル対等:
  - env: `MOOD__VARS__AAA_BBB=x` → `vars["aaa_bbb"]`（`env_nested_delimiter="__"`）
  - CLI: `--var aaa_bbb=x`（繰り返し可）
  - MCP: `build` / `watch` 引数 `vars`（mapping）
- 合流は pydantic-settings のソース間 deep-merge をそのまま使う（実測確認済み）: キー単位でマージされ、衝突は init（CLI / MCP）が env に勝つ。既存の「設定の読み込み優先順位」と同順
- **封筒 `MOOD__` はストアのキーに入らない**。プレフィックスは共有名前空間（プロセス環境）で自分宛ての値を仕分けるチャネル固有の作法であり（Java の `-D` に相当）、ストア内では全キーに共通で情報を持たないため剥がす。キーは小文字化して `vars.aaa_bbb` になる
- **env で書けるのは vars 直下一段のみ**。`dict[str, str]` の型検証が `MOOD__VARS__A__B` のネストを拒む挙動を、そのまま仕様として採る。背景:
  - 型を `dict[str, object]` に緩めるとネストは受かるが、pydantic-settings が env 値を JSON 解釈して `"42"` が int になり、「値は全て文字列」の契約が env 経由でだけ揺れる（実測）
  - ストアはフラットな文字列キーでドットはただの文字なので、深い階層キー（`vars.ci.run_id`）は CLI / MCP からドット入りキーとして渡せば成立する。制限は env チャネルの復号器の限界であって、ストアと照会には制限がない
- config はストアそのものではない: `config.vars` からストアキーへの合成（`vars.` 前置）は command / generator 層の明示的な一行で行う。config のフィールド位置（`config.vars`）がキーに漏れる経路は無い
