# メタドキュメンテーション

ツール自身のスキーマ定義やクエリ定義を、ツール自身で可視化する機能。

## 概要

ユーザプロジェクトの `schemaDir`、`queriesDir`、`contentsDir` の全体を source データとして扱い、ツール内蔵のスキーマ・クエリ・テンプレートを用いてツールを実行することで実現する。出力先は `meta.outDir`（Generator）および `meta.render.outDir`（Renderer）。

| | ツール内蔵（メタレベル） | ユーザプロジェクト |
|---|---|---|
| schema | JSON Schema の検証規則、YAML DSL の構文規則 | `schemaDir` の各ファイル |
| queries | schema / queries / contents を可視化するクエリ | `queriesDir` の各ファイル |
| templates | Query Design View、スキーマ一覧 等の可視化テンプレート | `templatesDir` の各ファイル |
| source（対象） | ユーザの `schemaDir` + `queriesDir` + `contentsDir` | ドメインデータ |

## できること

- ユーザの `schemaDir` を検証する（内蔵 schema で）
- ユーザの `queriesDir` を Query Design View として可視化する（内蔵 queries + templates で）
- ユーザの `contentsDir` をドメインビューとして可視化する（ユーザの queries + templates で）
