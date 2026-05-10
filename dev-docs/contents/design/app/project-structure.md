# プロジェクト構成

## External Design

### 背景: MS-Access アナロジー

contents / queries / templates の三層構造は MS-Access の Table / Query / Form・Report に対応する:

| MS-Access | このアプリ | 役割 |
|---|---|---|
| Table | `contents_dir` | 正規化されたデータ |
| Query (View) | `queries_dir` | データの整形・射影・結合の**定義** |
| Form / Report | `templates_dir` | 表現・レイアウト |

Access の Query は SQL で書く。テンプレートエンジンで Query を書くのは、Excel のセルに SQL を文字列として組み立てるようなもの。Query にはクエリ言語を使うべき。

さらに、Access の Query Design View は SQL を書かずに GUI でクエリを構築できる。queries/ を YAML DSL で定義することで、クエリ自体が構造化データとなり、このツール自身で可視化できる（dog fooding）。

### 背景: ソースコードリポジトリ内での配置

ソースコードリポジトリ内で使う場合、プロジェクトディレクトリを `docs/` 等のサブディレクトリに配置し `mood build docs/` のように指定する。`src/` や `tests/` との境界が明確になる。

独立したプロジェクトの場合は、プロジェクトルートに直接配置し `mood build .` を使う。

### 背景: .another-mood/ を CWD 直下に配置する理由

出力ディレクトリ `.another-mood/` は `<projectDir>`（入力ディレクトリ）の中ではなく、CWD（プロジェクトルート）直下に配置する。

- **入力ディレクトリはユーザのコンテンツ領域**: ツールから見れば参照先であり、生成物を書き込むべきでない
- `.` prefix はフレームワーク固有の作業領域を示す慣習（`.next/`, `.pytest_cache/` 等）に従う
- gitignore がシンプル（ルートに `/.another-mood/` の1行で済む）
- 入力がプロジェクト外（git submodule 等）にある場合でも破綻しない
- `contents_dir` を編集するメンバの視界に入らない

### 背景: 出力を `<projectDir>` ごとにサブディレクトリで分離する理由

`.another-mood/<projectDir>/` のように入力パスに対応するサブディレクトリを自動作成する。異なる `<projectDir>` を別プロセスで同時処理しても出力が衝突しない。サブディレクトリ名は CWD からの相対パスをそのまま使うため予測可能である。
