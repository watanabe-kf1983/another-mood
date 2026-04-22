# Pipeline

ユーザの定義・コンテンツから最終的なドキュメントを生成するパイプライン。

| ステージ | User Input | Upstream | Output |
|---|---|---|---|
| inspect_schema | schema_dir | — | inspect_schema_dir |
| normalize_contents | contents_dir, schema_dir ※1 | inspect_schema_dir | normalize_contents_dir |
| normalize_queries | queries_dir | inspect_schema_dir | normalize_queries_dir |
| compose | — | inspect_schema_dir ※2, normalize_contents_dir, normalize_queries_dir | compose_dir |
| generate | templates_dir | compose_dir | generate_dir |
| reconcile | — | generate_dir | reconcile_dir |
| render | — | reconcile_dir ※3 | render_dir |

dev モードでは User Input / Upstream ディレクトリの変更を Watch してステージを自動再実行する（`pipeline/base.py` 参照）。build モードでは依存順に直列実行する。※印は Watch 対象外の Input:

Upstream は前段ステージの Output であり、`BuildReport`（エラー伝播）の収集対象。User Input はユーザが直接編集するディレクトリで、`BuildReport` の収集対象外。

- ※1 schema_dir: バリデーションルールの読み込みに使うが、変更は SchemaInspector → inspect_schema_dir の経路で伝播するため Watch 不要
- ※2 inspect_schema_dir: 変更は SchemaInspector → inspect_schema_dir → Normalizer(contents) → normalize_contents_dir とカスケードし、normalize_contents_dir の変更で Composer が Kick されるため Watch 不要
- ※3 render は内部で Hugo 向け preparation Component を呼び出し、`reconcile_dir` → `prepare_dir` → Hugo に content を流す。preparation は Hugo 固有の adapter のため `pipeline/adapters/preparation.py` に置き、独立ステージとして expose しない

## 背景: ReportingStage と RenderStage は親ディレクトリを Watch

ReportingStage は `reconcile_dir` を、RenderStage は `reconcile_dir` をそれぞれ Watch する (`pipeline/stages.py`, `pipeline/render.py` 参照)。自身が興味を持つサブディレクトリ (`reconcile_dir/reports`, `reconcile_dir/data`) を直接指定していない。

理由: `exclusive_write` は Output ディレクトリの **子**を rmtree してから copytree で書き戻す設計 (`components/shared/dir_lock.py` 参照)。このとき子ディレクトリの inode が入れ替わる。**inotify の watch は inode に紐付く**ので、watch 対象が子ディレクトリだと rmtree で watch が無効化され、以降の event を受信できなくなる。親ディレクトリを Watch すれば親の inode は保持されるため、子の rmtree/recreate を跨いで event を継続受信できる。

他のカスケードステージは Output そのもの (≒ 親) を Watch しているので同じ問題は起きない。この例外的な 2 ステージだけが、サブディレクトリを必要とする位置付けから親 Watch 方式を取っている。

## 背景: Watch ライブラリは watchdog を採用

[watchdog](https://github.com/gorakhargosh/watchdog) を採用。過去に [watchfiles](https://github.com/samuelcolvin/watchfiles) を採用していた (PR #41) が、watchfiles は WSL を検出すると WSL1/WSL2 を区別せず強制 polling に切り替える挙動があり (issue #187、2022)、WSL2 環境で polling モードの event 取りこぼしが発生して watch が停止する問題があった (実測で `mood watch` 稼働中に concurrent `mood build` を当てると 10 回中 7 回最終状態が "failed" で固定)。

watchdog は Linux (WSL2 を含む) で inotify を使い、明示的に指定しない限り polling に落ちないため、WSL1 のような特殊ケースを考慮しなくてよい。OS ネイティブの event 通知機構を使う点は両ライブラリ共通だが、WSL の自動 polling 判定の挙動が異なる。

### watchdog 利用上の注意: 変更系 event のみに subscribe

`Watcher` クラス (`pipeline/adapters/watcher.py`) は `on_created / on_modified / on_deleted / on_moved` のみオーバーライドし、`on_opened / on_closed` は意図的に無視する。

inotify は `IN_OPEN / IN_CLOSE_NOWRITE` などの読み取り系 event も emit し、watchdog のデフォルト (`on_any_event`) はこれらも拾ってしまう。カスケード watcher の handler は upstream を `shutil.copytree` で読み込むため、**自身の読み込みが watch 対象上に open/close event を発生させ、watcher が自己トリガーし続ける** 挙動を引き起こす (watchfiles は library レベルで読み取り系を filter するため同じ問題は出ない)。変更系 event に絞ることで、cascade が自然に終息する。