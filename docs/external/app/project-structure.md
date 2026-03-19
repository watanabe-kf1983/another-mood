# プロジェクト構成

ユーザプロジェクトのディレクトリ構成。設定キーとデフォルトパスの詳細は [config-spec.md](config-spec.md) を参照。

## ディレクトリ構成

```
my-project/
  docs/
    index.md                   # ビルドコマンド + 生成物へのリンク
    definition/                # リーダが管理する定義類
      schema/                  # schemaDir: スキーマ定義（JSON Schema + references.yaml）
        entities.yaml          #   トップレベルキーがスキーマ名
        references.yaml        #   参照整合性定義（宣言的 FK）
      queries/                 # queriesDir: Query 定義（YAML DSL、Composer が評価）
      templates/               # templatesDir: ドキュメントテンプレート
      profiles.yaml            # profilesFile: プロファイル設定（ページ分割戦略）
    contents/                  # contentsDir: 実データ（YAML + Markdown。人間が書く、AI が直接編集）
  .reqs-builder/               # gitignore（生成物・中間生成物）
    tmp/
      normalized/              # Normalizer 出力（3ステージ分）
        schema/                # normalizedSchemaDir: schema の Normalizer 出力
        contents/              # normalizedContentsDir: contents の Normalizer 出力
        queries/               # normalizedQueriesDir: queries の Normalizer 出力
      views/                   # viewsDir: Composer 出力
    output/                    # outDir: Document Generator 出力
    render/                    # render.outDir: Document Renderer 出力
    meta/                      # ツールパイプライン出力
      output/                  # meta.outDir
      render/                  # meta.render.outDir
```

## 背景: MS-Access アナロジー

contents / queries / templates の三層構造は MS-Access の Table / Query / Form・Report に対応する:

| MS-Access | このアプリ | 役割 |
|---|---|---|
| Table | `contentsDir` | 正規化されたデータ |
| Query (View) | `queriesDir` | データの整形・射影・結合の**定義** |
| Form / Report | `templatesDir` | 表現・レイアウト |

Access の Query は SQL で書く。テンプレートエンジンで Query を書くのは、Excel のセルに SQL を文字列として組み立てるようなもの。Query にはクエリ言語を使うべき。

さらに、Access の Query Design View は SQL を書かずに GUI でクエリを構築できる。queries/ を YAML DSL で定義することで、クエリ自体が構造化データとなり、このツール自身で可視化できる（dog fooding）。

## 背景: docs/ 配下に配置する理由

ドキュメントはソースコードとともにリポジトリに格納されることが多い。`model/` や `presentation/` がプロジェクトルート直下にあると `src/` や `tests/` と混在する。`docs/` 配下にまとめることで、ソースコードとの境界が明確になる。

## 背景: .reqs-builder/ に生成物を隔離する理由

- `.` prefix はフレームワーク固有の作業領域を示す慣習（`.next/`, `.nuxt/` 等）に従う
- gitignore が自然で、「消しても再生成できるもの」という意図が明確
- `contentsDir` を編集するメンバの視界に入らない