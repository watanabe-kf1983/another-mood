# sbdb プロジェクト

## External Design

### sbdb プロジェクトとは

利用者がソースを書き、ツールに渡す単位となる一つのディレクトリ。CLI / MCP の `<project_dir>` はこれを指し、ツールはここを読んで文書を生成する。利用者向けの導線は `docs/guides.md` の Source structure 節。

### 構成

プロジェクトマニフェストと、利用者が書くディレクトリから成る:

- `sbdb.yaml` — プロジェクトが何であるか（表示名、フォーマット世代）を宣言するマニフェスト。これがあるディレクトリがsbdb プロジェクトであり、無ければツールは拒否する（[マニフェスト](20-sbdb-manifest.md)）
- `definition/` — スキーマ、ビュー、テンプレート
- `contents/` — データ

各パスは設定ではなく、sbdb フォーマットの `layout` 面が定める（[マニフェスト](20-sbdb-manifest.md#フォーマットを構成する契約面)）。利用者への約束は `docs/reference/cli.md` の Source layout 節。

### 三層構造

書くものは contents / views / templates の三層に分かれる:

| 層 | 役割 |
|---|---|
| `contents_dir` | 正規化されたデータ |
| `views_dir` | データの整形・射影・結合の**定義** |
| `templates_dir` | 表現・レイアウト |

層の境界: クエリはテンプレートに書かず、views に YAML DSL で定義する。クエリ自体が構造化データとなり、このツール自身で可視化できる（dog fooding）。三層の対応と DSL を選んだ理由は[背景](../../90-appendix/20-design/20-sbdb-project/10-sbdb-project.md#ms-access-アナロジー)。

### sbdb プロジェクトと生成物の分離

CLI は `<projectDir>` に生成物を書き込まず、出力 `.another-mood/` を CWD 直下に置く。入力ディレクトリはユーザのコンテンツ領域で、ツールから見れば参照先のため。利用者への約束は `docs/reference/cli.md` の `<project_dir>` 節、理由の全体は[背景](../../90-appendix/20-design/20-sbdb-project/10-sbdb-project.md#cli-が-another-mood-を-cwd-直下に配置する理由)。

MCP 経由は意図的な例外で、出力を `<projectDir>/.another-mood/` に置く。エージェントが確実に読み戻せる場所がそこしかないため（`mcp_server.py` の `_project_overrides`）。
