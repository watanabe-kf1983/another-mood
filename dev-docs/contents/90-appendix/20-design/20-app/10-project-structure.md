# プロジェクト構成 (appendix)

[プロジェクト構成](../../../20-design/20-app/10-project-structure.md) の背景。

## MS-Access アナロジー

contents / views / templates の三層構造は MS-Access の Table / Query / Form・Report に対応する:

| MS-Access | このアプリ | 役割 |
|---|---|---|
| Table | `contents_dir` | 正規化されたデータ |
| Query (View) | `views_dir` | データの整形・射影・結合の**定義** |
| Form / Report | `templates_dir` | 表現・レイアウト |

Access の Query は SQL で書く。テンプレートエンジンで Query を書くのは、Excel のセルに SQL を文字列として組み立てるようなもの。Query にはクエリ言語を使うべき。

さらに、Access の Query Design View は SQL を書かずに GUI でクエリを構築できる。ビューを YAML DSL で定義することで、クエリ自体が構造化データとなり、このツール自身で可視化できる（dog fooding）。

## CLI が .another-mood/ を CWD 直下に配置する理由

CLI では、出力ディレクトリ `.another-mood/` を `<projectDir>`（入力ディレクトリ）の中ではなく、CWD（プロジェクトルート）直下に配置する。

- **入力ディレクトリはユーザのコンテンツ領域**: ツールから見れば参照先であり、生成物を書き込むべきでない
- `.` prefix はフレームワーク固有の作業領域を示す慣習（`.next/`, `.pytest_cache/` 等）に従う
- gitignore がシンプル（ルートに `/.another-mood/` の1行で済む）
- 入力がプロジェクト外（git submodule 等）にある場合でも破綻しない
- `contents_dir` を編集するメンバの視界に入らない

入力ディレクトリ内出力に統一すれば、以下の帰結もろとも消える。それでも採らないのは、上の理由——とりわけ gitignore と視界——に正面から反するうえ、CWD 配下のディレクトリを `<projectDir>` にするのが CLI の主要ユースケースだからである。

帰結として、出力は `.another-mood/<CWD から見た projectDir>/` のようにサブディレクトリで分かれる（異なる `<projectDir>` を同時に処理しても衝突しない）。このキーは `<projectDir>` が CWD 配下にあって初めて定義できるので、CWD 外を指す場合（絶対パス・相対 `../` 脱出の両方）は `ProjectConfig.verify()` がエラーで拒否する — basename へフォールバックさせると `/a/proj` と `/b/proj` が同じ `.another-mood/proj/` に着地するため。`out_dir` / `site_dir` / `tap_dir` / `tmp_dir` は「どこに書き出すか」という別の関心で、CWD 外への出力に正当な用途があるため縛らない。
