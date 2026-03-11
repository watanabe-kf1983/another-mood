# メタドキュメンテーション

ツール自身のスキーマ定義やクエリ定義を、ツール自身で可視化する機能。

## 概要

ユーザプロジェクトの schema/、queries/、data/ の全体を source データとして扱い、ツール内蔵のスキーマ・クエリ・テンプレートを用いてツールを実行することで実現する。

| | ツール内蔵（メタレベル） | ユーザプロジェクト |
|---|---|---|
| schema | JSON Schema の検証規則、YAML DSL の構文規則 | schema/ の各ファイル |
| queries | schema / queries / data を可視化するクエリ | queries/ の各ファイル |
| templates | Query Design View、スキーマ一覧 等の可視化テンプレート | templates/ の各ファイル |
| source（対象） | ユーザの schema/ + queries/ + data/ | ドメインデータ |

## できること

- ユーザの schema/ を検証する（内蔵 schema で）
- ユーザの queries/ を Query Design View として可視化する（内蔵 queries + templates で）
- ユーザの data/ をドメインビューとして可視化する（ユーザの queries + templates で）

## dog fooding

Phase 3（Normalizer）・Phase 4（Composer）の開発自体がこのツールの dog fooding になる。Phase 2 で Document Generator が動いた時点から、ツール自身を使いながら標準 schema / queries / templates を開発できる。
