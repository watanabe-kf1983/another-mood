# 設定システム仕様

## External Design

### 設定の管轄範囲

設定システムが扱うのは**起動パラメータ**（どう実行し、どこへ出すか: `project_dir` / `out_dir` / `site_dir` / `tmp_dir` / `host` / `port`）のみ。

ソースレイアウト（`definition/schema.yaml` 等のパス群）は設定ではなく sbdb フォーマット世代が定めるプロジェクト構造であり、`resolve_layout`（`layout.py`）が導出する。個別に位置を上書きする手段は持たない — フォーマット世代を名乗りながらファイル位置を動かせるのは、宣言と矛盾するため。

### 設定の読み込み優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル（未実装 — [G2](node:/tasks/G/tasks/G2)）
3. 環境変数
4. CLI 引数

### 環境変数の綴り

プレフィックスは `MOOD_`。設定キーを大文字化して前置するだけで、`out_dir` → `MOOD_OUT_DIR`。実装は pydantic-settings の `env_prefix="MOOD_"`。

## 背景: preflight の順序

ソースパスの存在検証は `ProjectConfig.verify` ではなくレイアウト解決の後段で行い、失敗は `UserError` 系の precondition 例外として CLI / MCP 境界で出す（build-report には積まない）。パスが絶対であることの検査と `project_dir` の検証（`namespace_root` 配下 + 存在）だけが config 側に残る — manifest を読む前提条件のため。

あるべき preflight 順序: `project_dir` 検証 → manifest 読込（V1）→ 版ゲート（V4）→ レイアウト解決 → ソース存在検証。レイアウト解決を manifest 読込より後に置くのは、`resolve_layout` が将来 `sbdb_version` で版ディスパッチする拡張点であり、非対応版プロジェクトには「Source paths not found」より先に「非対応版」を出すべきため（詳細は [60-sbdb-manifest](node:/prose/20-design/20-app/60-sbdb-manifest)）。

## Proposals

### 設定ファイル (G2)

- ファイル名: `another-mood.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON

### ビルド時情報の供給機構 (P14 の config 側)

テンプレート照会関数 `build_info`（[30-template-spec.md](../70-generator/30-template-spec.md) の Proposals 参照）へ渡す利用者注入値 `vars.*` を、config 層で受ける。

- `ProjectConfig` に `vars: dict[str, str]` フィールドを追加。供給は三チャネル対等:
  - env: 綴りは下の「env チャネルの綴り」で決める
  - CLI: `--var aaa_bbb=x`（繰り返し可）
  - MCP: `build` / `watch` 引数 `vars`（mapping）
- 合流は pydantic-settings のソース間 deep-merge をそのまま使う（実測確認済み）: キー単位でマージされ、衝突は init（CLI / MCP）が env に勝つ。既存の「設定の読み込み優先順位」と同順
- **封筒 `MOOD_` はストアのキーに入らない**。プレフィックスは共有名前空間（プロセス環境）で自分宛ての値を仕分けるチャネル固有の作法であり（Java の `-D` に相当）、ストア内では全キーに共通で情報を持たないため剥がす。キーは小文字化して `vars.aaa_bbb` になる
- **env で書けるのは vars 直下一段のみ**。深い階層キー（`vars.ci.run_id`）は CLI / MCP からドット入りキーとして渡せば成立する（ストアはフラットな文字列キーでドットはただの文字）。制限は env チャネルの復号器の限界であって、ストアと照会には制限がない
  - 型を `dict[str, object]` に緩めればネストは受かるが、pydantic-settings が env 値を JSON 解釈して `"42"` が int になり、「値は全て文字列」の契約が env 経由でだけ揺れる（実測）ので採らない
- config はストアそのものではない: `config.vars` からストアキーへの合成（`vars.` 前置）は command / generator 層の明示的な一行で行う。config のフィールド位置（`config.vars`）がキーに漏れる経路は無い

#### env チャネルの綴り（未決）

`MOOD_VARS__GIT_SHA` と `MOOD_VARS_GIT_SHA` のどちらを採るか。G14 で確定したトップレベルの `MOOD_` とは独立に選べる。実測した事実:

- pydantic-settings の `env_nested_delimiter` は**分割文字**なので、語区切りと同じ `_` は使えない。`env_nested_delimiter="_"` の下では `MOOD_VARS_GIT_SHA` が `vars.git.sha` と解釈され、`dict[str, str]` の検証に落ちる。通るのは一語のキー（`MOOD_VARS_SHA` → `vars["sha"]`）だけで、`git_sha` / `run_id` / `build_number` といった実際に使いたい名前が全滅する
- したがって `MOOD_VARS_GIT_SHA` を成立させるにはカスタム settings source が要る。`MOOD_VARS_` という固定リテラルを剥がして残りを小文字化するだけで、**分割しないので曖昧性は無い**。これはトップレベルのプレフィックスが既に使っている機構と同一で、それを一段下に適用するもの。先例は Hugo の `HUGO_PARAMS_*`
- 二案の比較軸: `__` は `env_nested_delimiter="__"` 一行で済むが、封筒＝階層でないという上の整理と綴りがずれる。リテラル剥がしは綴りが素直になる代わりに実装（20〜30 行）と、`MOOD_VARS_` が予約語になること（`vars_*` という名のトップレベルフィールドを将来作れない）を負う。上で「env は vars 直下一段のみ」と決めている以上、`__` の多段表現力は使われない
