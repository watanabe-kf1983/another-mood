# CLI

`mood` は Another Mood のエントリポイントとなるコマンドラインツール。プロジェクトの初期化（`init`）、一括ビルド（`build`）、ファイル監視 + ライブプレビュー（`watch`）の 3 サブコマンドを提供する。

すべてのサブコマンドは第一位置パラメータ `<project_dir>` で処理対象ディレクトリを受け取る。典型的な使い方は、プロジェクトディレクトリで `.` を指定する形:

```bash
mood init .
mood build .
mood watch .
```

## コマンド一覧

| コマンド | 用途 |
|---|---|
| [`mood init <project_dir>`](#init) | サンプル付きのプロジェクト雛形を生成する |
| [`mood build <project_dir>`](#build) | 全段を 1 度実行し、Markdown と HTML を生成する |
| [`mood watch <project_dir> [--port <port>]`](#watch) | ファイル変更を監視して再ビルドし、Hugo server でプレビューを配信する |

## 共通引数: `<project_dir>`

`<project_dir>` は CWD からの相対パスで指定する。指定したパスを起点に入力パスを解決し、CWD 直下の `.another-mood/<project_dir>/` に出力する。

### 入力パスの解決

入力パス（schema ファイル / contents・queries・templates の各ディレクトリ）は `<project_dir>` を基準に解決される。デフォルト配置は次の通り:

| 種類 | デフォルト | 環境変数 |
|---|---|---|
| スキーマ | `<project_dir>/definition/schema.yaml` | `RB_SCHEMA_FILE` |
| コンテンツ | `<project_dir>/contents` | `RB_CONTENTS_DIR` |
| クエリ | `<project_dir>/definition/queries` | `RB_QUERIES_DIR` |
| テンプレート | `<project_dir>/definition/templates` | `RB_TEMPLATES_DIR` |

`build` / `watch` 起動時にこれらのパスが存在しないとエラーになり、終了コード 1 で停止する。

### 出力パスの解決

出力ディレクトリは `<project_dir>` を基準に展開し、CWD 直下の `.another-mood/<project_dir>/` 配下に配置される:

| 種類 | デフォルト | 環境変数 |
|---|---|---|
| 中間出力（ステージごと） | `.another-mood/<project_dir>/tmp` | `RB_TMP_DIR` |
| Generator 出力（最終 Markdown） | `.another-mood/<project_dir>/output` | `RB_OUT_DIR` |
| Renderer 出力（最終 HTML） | `.another-mood/<project_dir>/render` | `RB_RENDER_DIR` |

異なる `<project_dir>` を別プロセスで同時に処理しても出力先が衝突しないよう、入力パスに対応するサブディレクトリが自動的に作られる。

## init

プロジェクトの雛形を生成する。

```bash
mood init <project_dir>
```

`<project_dir>` 配下に、内蔵の starter テンプレート（schema / contents / queries / templates の最小サンプル一式）をコピーする。`<project_dir>` が存在しない場合は親ディレクトリごと作成される。

**既存ファイルの上書き**: 同名のファイルが既にある場合、上書きはせず警告を表示してスキップする。

```
warning: skipped (already exists): ./definition/schema.yaml
```

すべてのファイルが新規作成された場合は終了コード 0、いずれか 1 つでもスキップされた場合は終了コード 1 で終了する。これは「初回実行時に空ディレクトリへ書き込めたか」を CI 等から判定できるようにするためで、既存プロジェクトに対して `init` を再実行しても破壊的な変更は起きない。

## build

全段を 1 度実行して、Markdown と HTML を生成する。

```bash
mood build <project_dir>
```

実行内容:

1. `<project_dir>/definition/schema.yaml` を読み込み、`<project_dir>/contents` を正規化
2. `<project_dir>/definition/queries` のクエリを評価して view を構築
3. `<project_dir>/definition/templates` を使って Markdown を `output/` に書き出す
4. `output/` を Hugo に渡して HTML を `render/` に書き出す

すべてのステージが成功すれば終了コード 0、いずれかのステージでエラーが発生すれば終了コード 1 で終了する。

**用途**:

- CI / リリースでの一括生成
- コーディングエージェントとの協業。エージェントがファイルを編集した後に `mood build` を実行し、終了コードで成否を判定する。ブラウザ側は VS Code Live Server 等で `render/` を常時配信し、人がリロードで確認するワークフローに合う

## watch

ファイル変更を監視して自動再ビルドし、Hugo server でライブプレビューを配信する。

```bash
mood watch <project_dir> [--port <port>]
```

入力パス（schema ファイル / contents・queries・templates の各ディレクトリ）の変更を検知すると、影響のあるステージのみを再実行する。Hugo server はファイル更新を検知してブラウザ側を自動リロードする。`Ctrl+C` で停止する。

```
$ mood watch .
Press Ctrl+C to stop.
```

### `--port`

Hugo server が listen するポートを指定する。デフォルトは `1313`（環境変数 `RB_PORT` でも上書き可能）。

```bash
mood watch . --port 8080
```

複数の `<project_dir>` を同時に watch したい場合は、複数プロセスを起動する。出力ディレクトリは `<project_dir>` ごとに自動的に分離されるため衝突しないが、ポートは競合するので 2 つ目以降は `--port` で別ポートを指定する必要がある。

## 設定の上書き

設定キーはすべてデフォルト値を持つが、環境変数で個別に上書きできる。

### 環境変数 (`RB_*`)

各設定キーは `RB_` プレフィックス + 大文字スネークケースの環境変数で上書きできる。環境変数で指定した値はそのままパスとして使われ、`<project_dir>` を基準とした既定値の組み立てロジックは適用されない。

```bash
RB_CONTENTS_DIR=/abs/path/to/contents mood build .
RB_PORT=8080 mood watch .
```

### 主要キーと既定値

| キー | 既定値 | 環境変数 | CLI |
|---|---|---|---|
| `project_dir` | （引数で必須） | — | 第一位置パラメータ |
| `schema_file` | `<project_dir>/definition/schema.yaml` | `RB_SCHEMA_FILE` | — |
| `contents_dir` | `<project_dir>/contents` | `RB_CONTENTS_DIR` | — |
| `queries_dir` | `<project_dir>/definition/queries` | `RB_QUERIES_DIR` | — |
| `templates_dir` | `<project_dir>/definition/templates` | `RB_TEMPLATES_DIR` | — |
| `tmp_dir` | `.another-mood/<project_dir>/tmp` | `RB_TMP_DIR` | — |
| `out_dir` | `.another-mood/<project_dir>/output` | `RB_OUT_DIR` | — |
| `render_dir` | `.another-mood/<project_dir>/render` | `RB_RENDER_DIR` | — |
| `port` | `1313` | `RB_PORT` | `--port`（`watch` のみ） |
