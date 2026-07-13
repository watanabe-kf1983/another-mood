# 設定システム仕様

## External Design

### 設定の読み込み優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル（未実装 — [G2](node:/tasks/G/tasks/G2)）
3. 環境変数
4. CLI 引数

### 作業ディレクトリ（tmp）

`tmp_dir`（ビルドの中間作業ディレクトリ）は既定でシステム temp 配下のセッション固有ディレクトリ（`tempfile.mkdtemp`）に置かれる。`RB_TMP_DIR` で固定パスに向けられる。

後始末は mode で分かれる:

- **build**: 実行ごとに作り、成功時・および UserError のみの失敗時に削除する。内部エラー（tool のバグ / 環境要因）のときだけ保持し、パスをログに出す（中間状態がデバッグに役立つ唯一のケース）。
- **watch**: 同様に作るが削除しない。セッションが少なく長寿命で堆積が緩やかなため、OS の temp 掃除に委ねる。
- **`RB_TMP_DIR` 明示指定時**: どちらの mode でも honor し、削除しない（lifecycle は利用者に委ねる）。

## Proposals

### 設定ファイル (G2)

- ファイル名: `another-mood.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON

### render.customServer.command (G3)

> **未実装** — Phase 10 タスク [G3](node:/tasks/G/tasks/G3)。

カスタムレンダリングサーバのコマンドを設定すると、Hugo の代わりに使用される。詳細は下表。

### 処理対象ディレクトリの CWD 配下制約 (G8)

> **未実装** — タスク [G8](node:/tasks/G/tasks/G8)。

`<projectDir>` 引数および `RB_*` で渡されるパスは、CWD 配下のみを許可する。CWD 外のパス（`../other-repo/docs` や絶対パス `/some/elsewhere/docs` 等）はエラーとして拒否する。

現状は `_another_mood_root` (`config.py`) が CWD 外の絶対パスを受けた場合に basename を採用してフォールバックする実装になっており、エラーにはしない。

### watch の出力 publish 隔離 (G9)

> **一部実装** — タスク [G9](node:/tasks/G/tasks/G9)。作業 tmp のシステム temp 隔離は実装済み（External Design「作業ディレクトリ（tmp）」節）。残るのは watch の出力 publish の隔離。

out（md）/ render（html）は publish の宛先であり、watch では既定で publish しない。

#### out / render — watch は既定で publish しない

- **watch 既定（無指定）**: プロジェクトに何も書かない。プレビューは tmp（`prep_dir/data`）から `hugo serve` が配信し、診断ビュー（`__db/`）もプレビューのページとして見る。ファイルが欲しければ watch を止めずに `mood build` を打てばよい（書き先が分かれるので衝突しない）。
- **watch `--out-dir <path>`（opt-in）**: 再ビルドごとに **md 出力ツリーだけ**をそこへ publish する。宛先の指定が opt-in を兼ねる（boolean フラグは置かない）。html（render_dir）は watch では publish しない（`--render-dir` は watch に付けない）— watch の html 消費者はライブサーバで、静的 html が欲しければ `mood build`。
- **命名は既存 build に合わせる**: `--out-dir` / `RB_OUT_DIR` / `out_dir` を流用し、watch 専用キー（`RB_WATCH_OUTPUT_DIR` 等）は作らない。mode 差は**デフォルト値だけ** — build は `.another-mood/<project>/output`、watch は「無し（無 publish）」。
- **build は不変**: `--out-dir` / `--render-dir` とデフォルト `.another-mood/<project>/{output,render}` は据え置き。tmp が mkdtemp へ移る結果、`.another-mood/<project>/` には output/ と render/ のみ残る。
- 内部: watch 既定でも publish ステージ自体は走る（reports / error propagation のため。レポートは tmp 側から読み、dist コピーの有無と独立）。dist へのコピーだけ空にする。`BuildResult.out_dir` は watch では未使用のため空でよい。

> **背景.** watch と build の並行実行は実運用シナリオ（[30-pipeline.md](../30-pipeline.md) の watchdog 節に実測記録）だが、作業ディレクトリを共有する現状では、build や出力ファイルの読み出しが watch 側 publish（rmtree → copytree）の窓とレースする。hugo server / Vite dev が成果物ディレクトリに書かないのと同じ分業 — watch = プレビュー、build = 成果物 — を採る。AI との協業では特に、プロジェクトの output/ を「明示的な build だけが書く場所」に保つことで、agent が読む診断ビューの鮮度が決定的になる。in-process のメモリ FS（PyFilesystem2 等、hugo server の afero MemMapFs 相当）は Hugo subprocess から見えないため不採用 — システム temp への実パス書き込みで同じ利用者体験が得られる（Linux では tmpfs の恩恵をそのまま受ける）。

付帯作業: `docs/guides.md` 等の「書きながら `output/__db/` を確認」という案内を、watch 利用者向けに「プレビューの `/__db/` ページを見る。ファイルとして欲しければ `mood build`」へ書き換える（build / agent 向けはファイルのまま）。`--out-dir` にプロジェクトの `output/` を指せば従来同様のレースに戻ることを docs に一言注意する。

### 未実装の config キー

| キー | 型 | デフォルト | 環境変数 | CLI | タスク | 説明 |
|------|-----|---------|----------|-----|------|------|
| `render.customServer.command` | string | (なし) | `RB_RENDER_CUSTOM_SERVER_COMMAND` | — | G3 | カスタムレンダリングサーバのコマンド。設定時は Hugo の代わりに使用 |
