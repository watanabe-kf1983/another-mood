# 外部仕様

ユーザ向けのファイルフォーマット・機能仕様。

## normalizer

- [schema-spec.md](normalizer/schema-spec.md) — スキーマの設計判断（Entity/ObjectType、コンポジション vs 集約、エラー報告）と未実装 references
- [markdown-parser-spec.md](normalizer/markdown-parser-spec.md) — Markdown パーサーの設計判断と未実装機能（A1〜A6）

## composer

- [queries-spec.md](composer/queries-spec.md) — クエリ DSL の設計判断と未実装機能（E1〜E6, M1）

## generator

- [template-spec.md](generator/template-spec.md) — テンプレートの設計判断（ChainableUndefined）と未実装機能（C4）
- [anchor-spec.md](generator/anchor-spec.md) — アンカー（key/ID 体系、フラットマップ、リンク解決）
- [paging-spec.md](generator/paging-spec.md) — ページ分割（paging.yaml、プロファイル、分割ルール）

## app

- [project-structure.md](app/project-structure.md) — プロジェクト構成の設計判断（MS-Access アナロジー、`.another-mood/` 配置等）
- [cli-spec.md](app/cli-spec.md) — CLI 仕様
- [config-spec.md](app/config-spec.md) — 設定システム
- [mcp-design.md](app/mcp-design.md) — MCP サーバ設計
- [meta-documentation.md](app/meta-documentation.md) — メタドキュメンテーション（ツール自身の可視化）
