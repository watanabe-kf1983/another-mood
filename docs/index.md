# Documentation

## [background/](background/)

プロジェクトの背景と経緯。

- [product.md](background/product.md) — 製品ビジョンとコア設計判断
- [reqs-builder-original.md](background/reqs-builder-original.md) — 初期構想（要件定義ツール時代）
- [roadmap.md](background/roadmap.md) — ロードマップ

## [external/](external/index.md)

ユーザ向け外部仕様。詳細は [external/index.md](external/index.md) を参照。

- [normalizer/](external/normalizer/) — スキーマ定義、Markdownパーサー
- [composer/](external/composer/) — YAML DSL クエリ仕様
- [generator/](external/generator/) — テンプレート、アンカー、ページ分割
- [app/](external/app/) — CLI、設定、MCP、メタドキュメンテーション

## [internal/](internal/)

内部設計・実装仕様。

- [architecture.md](internal/architecture.md) — アーキテクチャ概要
- [glossary.md](internal/glossary.md) — 用語集（JSON データモデル等）
- [pipeline/](internal/pipeline/) — パイプライン構成、プロセス連携、StageRunner
- [components/](internal/components/) — Normalizer、Composer、Generator、Renderer

## 開発規約

[DEVELOPMENT.md](../DEVELOPMENT.md) に統合済み。
