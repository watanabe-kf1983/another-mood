# Architecture

## アーキテクチャ概要

3コンポーネント + レンダラー構成:

**Normalizer**
スキーマ定義に基づいてデータを検証し、辞書形式を配列形式に正規化する。
Markdown ファイルは内蔵の prose スキーマに従って自動的に正規化する（[markdown-parser-spec.md](../external/normalizer/markdown-parser-spec.md) 参照）。
`--strict` モードでは参照整合性もチェックする。
IN: スキーマ定義 (`model/schema/`)、実データ (`model/data/*.yaml`, `model/data/*.md`)
OUT: 正規化済みデータ (`output/model/normalized/`)

**Composer**
正規化済みデータを自動的にビューとしてパススルーし、さらに YAML DSL のクエリがあれば評価して追加のビューを生成する。
IN: 正規化済みデータ (`output/model/normalized/`)、クエリ定義 (`model/queries/`、任意)
OUT: ビュー (`output/model/views/`)

**Document Generator**
ビューデータをテンプレートに流し込み、ページ分割設定に従って Markdown ファイルを生成する。
IN: ビュー (`output/model/views/`)、テンプレート (`presentation/templates/`)、ページ分割設定 (`presentation/paging.yaml`)
OUT: Markdown ドキュメント (`output/documents/`)

**Document Renderer**
生成された Markdown を HTML にレンダリングする。
IN: Markdown ドキュメント (`output/documents/`)
OUT: HTML (`output/rendered/`)

各コンポーネントはファイル監視のトリガーが異なるため、別プロセスとして動作する。data/ を変更すると normalized/ → views/ → documents/ とカスケードで更新される。

パイプライン構成とプロセス連携:
- [pipeline/pipeline.md](pipeline/pipeline.md) — パイプライン構成
- [pipeline/process-coordination.md](pipeline/process-coordination.md) — プロセス間連携
- [pipeline/stage-runner.md](pipeline/stage-runner.md) — StageRunner（出力の原子性・順序性）

各コンポーネントの処理フローと技術選定:
- [components/normalizer.md](components/normalizer.md)
- [components/composer.md](components/composer.md)
- [components/generator.md](components/generator.md)
- [components/renderer.md](components/renderer.md)

## ユーザプロジェクト構成

```
my-project/
  model/
    schema/              # スキーマ定義（JSON Schema + references.yaml）
      entities.yaml      # スキーマ定義（トップレベルキーがスキーマ名）
      references.yaml    # 参照整合性定義（Snowflake 式宣言的 FK）
    data/                # 実データ（YAML + Markdown。人間が書く、AI が直接編集）
    queries/             # Query 定義: YAML DSL（Composer が評価）
  presentation/
    templates/           # ドキュメントテンプレート（Document Generator が読む）
    paging.yaml          # ページ分割戦略（Document Generator が読む）
```

## 背景: MS-Access アナロジー

data / queries / templates の三層構造は MS-Access の Table / Query / Form・Report に対応する:

| MS-Access | このアプリ | 役割 |
|---|---|---|
| Table | data/ | 正規化されたデータ |
| Query (View) | queries/ | データの整形・射影・結合の**定義** |
| Form / Report | templates/ | 表現・レイアウト |

Access の Query は SQL で書く。テンプレートエンジンで Query を書くのは、Excel のセルに SQL を文字列として組み立てるようなもの。Query にはクエリ言語を使うべき。

さらに、Access の Query Design View は SQL を書かずに GUI でクエリを構築できる。queries/ を YAML DSL で定義することで、クエリ自体が構造化データとなり、このツール自身で可視化できる（dog fooding）。

## 設計判断

1. **既存ツールを最大限活用** - 車輪の再発明を避ける
2. **スキーマ定義は言語非依存な資産** - YAML/JSON Schema として Git 管理
3. **周辺ツールは差し替え可能に** - 出力形式、レンダリングツール等は疎結合に
4. **クエリは YAML DSL** - クエリ自体が構造化データ、ツール自身で管理・可視化可能
5. **CUD は AI 直接編集** - ツールは YAML を読むだけ、CRUD API は提供しない
6. **スキーマは JSON Schema** - 独自形式を避け、additionalProperties で辞書→配列の正規化を行う

