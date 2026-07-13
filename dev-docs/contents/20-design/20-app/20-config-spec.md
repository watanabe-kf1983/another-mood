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

### watch の作業ディレクトリ隔離 (G9)

> **未実装** — タスク [G9](node:/tasks/G/tasks/G9)。

`mood watch` の作業ディレクトリ（tmp / render / output）を、プロジェクトの `.another-mood/` からシステム temp 配下の**セッション固有ディレクトリ**へ移す。プロジェクトディレクトリへの出力は既定では行わず、`--outputDir <path>` が指定されたときのみ、再ビルドごとに output（md 出力ツリー）をそこへ publish する — **宛先の指定が opt-in を兼ねる**（boolean フラグは置かない）。render / tmp は常にセッション temp。

- 既定（無指定）: watch はプロジェクトに何も書かない。プレビューはセッション temp から配信し、診断ビュー（`__db/`）もプレビューのページとして見る。ファイルが欲しければ watch を止めずに `mood build` を打てばよい（書き先が分かれるので衝突しない）
- セッション固有ディレクトリにより、同一プロジェクトの複数 watch（別ポート）が自然に可能になる。初回はコールドスタート（全ビルド）。終了時に best-effort で掃除する

> **背景.** watch と build の並行実行は実運用シナリオ（[30-pipeline.md](../30-pipeline.md) の watchdog 節に実測記録）だが、作業ディレクトリを共有する現状では、build や出力ファイルの読み出しが watch 側 publish（rmtree → copytree）の窓とレースする。hugo server / Vite dev が成果物ディレクトリに書かないのと同じ分業 — watch = プレビュー、build = 成果物 — を採る。AI との協業では特に、プロジェクトの output/ を「明示的な build だけが書く場所」に保つことで、agent が読む診断ビューの鮮度が決定的になる。in-process のメモリ FS（PyFilesystem2 等、hugo server の afero MemMapFs 相当）は Hugo subprocess から見えないため不採用 — システム temp への実パス書き込みで同じ利用者体験が得られる（Linux では tmpfs の恩恵をそのまま受ける）。

付帯作業: `docs/guides.md` 等の「書きながら `output/__db/` を確認」という案内を、watch 利用者向けに「プレビューの `/__db/` ページを見る。ファイルとして欲しければ `mood build`」へ書き換える。`--outputDir` にプロジェクトの `output/` を指せば従来同様のレースに戻ることは docs に一言注意する。

検討事項（着手時に再検討）: `mood build` の tmp も同様にシステム temp へ移せる。tmp は利用者も agent も参照せず（guides.md は案内していない）、プロジェクト内にあると agent のファイル検索に中間コピーがノイズとして混入する。build は毎回フルビルドで tmp にビルド間の状態を持たないため、形は二択 — (a) セッション固有ディレクトリを成功時に削除・失敗時は残して実パスをログに出す（残骸ゼロ、デバッグ導線維持）、(b) プロジェクト絶対パスをキーにした安定ディレクトリを毎回上書き（実装最小・事後デバッグが既定で可能、フットプリントは有界）。いずれもクリーンアップの仕組みは自作せず、取り残しは OS の temp 掃除（systemd-tmpfiles / macOS の定期 purge / tmpfs の再起動クリア）に任せる。

### 未実装の config キー

| キー | 型 | デフォルト | 環境変数 | CLI | タスク | 説明 |
|------|-----|---------|----------|-----|------|------|
| `render.customServer.command` | string | (なし) | `RB_RENDER_CUSTOM_SERVER_COMMAND` | — | G3 | カスタムレンダリングサーバのコマンド。設定時は Hugo の代わりに使用 |
| `watch.outputDir` | string | (なし = 無出力) | `RB_WATCH_OUTPUT_DIR` | `--outputDir` | G9 | watch が md 出力を publish する先。無指定なら watch はプロジェクトに書かない |
