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

### render.customServer.command (G3)

> **未実装** — Phase 10 タスク [G3](node:/tasks/G/tasks/G3)。

カスタムレンダリングサーバのコマンドを設定すると、Hugo の代わりに使用される。詳細は下表。

### 処理対象ディレクトリの CWD 配下制約 (G8)

> **未実装** — タスク [G8](node:/tasks/G/tasks/G8)。

`<projectDir>` 引数および `RB_*` で渡されるパスは、CWD 配下のみを許可する。CWD 外のパス（`../other-repo/docs` や絶対パス `/some/elsewhere/docs` 等）はエラーとして拒否する。

現状は `_another_mood_root` (`config.py`) が CWD 外の絶対パスを受けた場合に basename を採用してフォールバックする実装になっており、エラーにはしない。

### 作業ディレクトリのシステム temp 隔離 (G9)

> **未実装** — タスク [G9](node:/tasks/G/tasks/G9)。

作業ディレクトリ（tmp）を、プロジェクトの `.another-mood/` からシステム temp（`tempfile.mkdtemp`）へ移す。watch と build で「溜まり方」が異なるため後始末ポリシーを分ける。out（md）/ render（html）は publish の宛先であり、watch では既定で publish しない。

#### tmp: watch — mkdtemp、消さない

`tempfile.mkdtemp(prefix="another-mood-")` でセッション固有ディレクトリを作り、**明示的な削除はしない**（`finally` も signal handler も置かない）。取り残しは OS の temp 掃除に委ねる。

- 理由: watch は「起動して放置」でセッションが少なく長寿命 → 作りっぱなしでも堆積は緩やか。「temp に作りっぱなし・OS が回収」は temp の設計思想どおりで、pip / systemd-private / go-build 等と同じ ecosystem 標準。`mkdtemp` は `0700`・予測不能名で作られるため、共有 `/tmp` に予測可能パスを置く安全性懸念も生じない。
- セッション固有ディレクトリにより、同一プロジェクトの複数 watch（別ポート）が自然に隔離される（port が実質の識別子で、同一 port の二重起動は bind 失敗で発生しない）。各セッションの初回はコールドスタート（全ビルド）。

> **背景: 掃除の backstop は環境で異なるが実害は小さい.** systemd 環境は `systemd-tmpfiles`（`/tmp` 約10日）、tmpfs な `/tmp` は再起動、macOS は約3日、コンテナ / CI はライフサイクルで一掃される。ネイティブ Windows や reaper の無い素の Linux は自動回収しないが、他の全 temp 利用アプリと同条件であり、watch のフットプリントは小さい。よって全環境で「消さない」を採る。

#### tmp: build — mkdtemp、成功／UserError 失敗で削除

build も `tempfile.mkdtemp` を使うが、watch と違い後始末する。build は agent の `edit → build → 修正 → build` ループで高頻度に走り、消さないと急速に堆積するため。

- ポリシー: **成功時・および UserError のみの失敗時は削除**（どちらも高頻度）。**非UserError（tool のバグ / 環境要因）のときだけ保持し、実パスをログに出す**（稀 → 堆積せず、中間状態がデバッグに役立つ唯一のケース）。debug mode 等の別スイッチは設けない（「debug したいとき＝非UserError のとき」で保持条件に含まれる）。
- 成功時に消して失うものは無い: 成果物と診断ビュー（`__db/`）は out_dir に publish 済みで、tmp は中間物のみ。
- 非UserError の判定はコードに既にある: UserError は `ErrorEntry(traceback=None)`、それ以外の例外は `ErrorEntry` に Python traceback を載せる（`shared/component/build_report.py` の `_entries_from_exception`）。traceback フィールドは `BuildResult.errors` に素通しされるので、`any(e.traceback for e in result.errors)` で判定できる。これを `BuildResult.has_internal_error()`（下支えに `ErrorEntry.is_internal`）として型に持たせる。捕捉漏れの例外が `build()` から送出された場合も保持する。
- `ENAMETOOLONG` は `PathTooLongError`（UserError）に再分類済み（`errors.py`）＝ 削除対象。パス長は利用者が直せる。

tmp 生成と後始末の置き場は **command 層**（CLI / MCP build 双方に効かせる）。`config.tmp_dir` への mkdtemp パス注入は、mode を区別できず副作用も生じる `_fill_defaults`（validator）ではなく command 層で行う。

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
