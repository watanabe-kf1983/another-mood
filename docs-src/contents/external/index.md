# 外部仕様

ユーザ向けのファイルフォーマット・機能仕様。

## normalizer

- [schema-spec.md](normalizer/schema-spec.md) — スキーマ定義（JSON Schema + references.yaml + 正規化ルール）
- [markdown-parser-spec.md](normalizer/markdown-parser-spec.md) — Markdown パーサー（データソースとしての Markdown）

## composer

- [queries-spec.md](composer/queries-spec.md) — クエリ定義（YAML DSL）

## generator

- [template-spec.md](generator/template-spec.md) — テンプレート（root、section タグ、パーシャル、エスケープ）
- [anchor-spec.md](generator/anchor-spec.md) — アンカー（key/ID 体系、フラットマップ、リンク解決）
- [paging-spec.md](generator/paging-spec.md) — ページ分割（paging.yaml、プロファイル、分割ルール）

## app

- [project-structure.md](app/project-structure.md) — プロジェクト構成（ディレクトリ配置、definition/contents 分離）
- [cli-spec.md](app/cli-spec.md) — CLI 仕様
- [config-spec.md](app/config-spec.md) — 設定システム
- [mcp-design.md](app/mcp-design.md) — MCP サーバ設計
- [meta-documentation.md](app/meta-documentation.md) — メタドキュメンテーション（ツール自身の可視化）
