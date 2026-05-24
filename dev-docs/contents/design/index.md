# Design

設計仕様。各ファイル内は以下の構造（該当セクションのみ）:

- `## External Design` — 利用者から見える振る舞いの設計判断
- `## Internal Design` — 内部実装の設計判断
- `## Proposals` — 未実装機能（task に対応）

## 横断

- [architecture.md](architecture.md) — アーキテクチャ概要
- [json-data-model.md](json-data-model.md) — JSON データモデル
- [pipeline.md](pipeline.md) — パイプライン構成

## normalizer

- [schema-spec.md](normalizer/schema-spec.md) — スキーマの設計判断（Entity/ObjectType、コンポジション vs 集約）と未実装 references
- [markdown-parser-spec.md](normalizer/markdown-parser-spec.md) — Markdown パーサーの設計判断と未実装機能（A1〜A6）
- [normalizer.md](normalizer/normalizer.md) — Normalizer 全般の未実装機能（H1, H2 / D8, D9）

## composer

- [queries-spec.md](composer/queries-spec.md) — クエリ DSL の設計判断と未実装機能（E1〜E6）

## generator

- [template-spec.md](generator/template-spec.md) — テンプレートの設計判断（ChainableUndefined）と未実装機能（C4）
- [anchor-spec.md](generator/anchor-spec.md) — アンカー（アンカー ID 体系、リンク記法、リンク解決）
- [paging-spec.md](generator/paging-spec.md) — ページ分割（paging.yaml、プロファイル、分割ルール）
- [generator.md](generator/generator.md) — Generator 内部設計（内蔵ルートテンプレート、Reconcile）と未実装機能（B1〜B7 リンク解決・親参照等）

## app

- [project-structure.md](app/project-structure.md) — プロジェクト構成の設計判断（MS-Access アナロジー、`.another-mood/` 配置等）
- [config-spec.md](app/config-spec.md) — 設定システムの設計判断と未実装 config キー（CLI / 環境変数 / 設定ファイル / パス制約）
- [mcp-design.md](app/mcp-design.md) — MCP の設計判断（External + Internal、各種背景）
- [meta-documentation.md](app/meta-documentation.md) — メタドキュメンテーション（ツール自身の可視化）
- [system-dev-docs.md](app/system-dev-docs.md) — システム開発ドキュメント（S カテゴリ、ユーザ-authored 設計書 artifact 群）
