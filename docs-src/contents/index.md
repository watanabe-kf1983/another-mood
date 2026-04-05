# Documentation

## background

プロジェクトの背景と経緯。

- [product.md](background/product.md) — 製品ビジョンとコア設計判断
- [reqs-builder-original.md](background/reqs-builder-original.md) — 初期構想（要件定義ツール時代）
- [roadmap.md](background/roadmap.md) — ロードマップ

## external

ユーザ向け外部仕様。詳細は [external/index.md](external/index.md) を参照。

- normalizer — スキーマ定義、Markdownパーサー
- composer — YAML DSL クエリ仕様
- generator — テンプレート、アンカー、ページ分割
- app — CLI、設定、MCP、メタドキュメンテーション

## internal

内部設計・実装仕様。

- [architecture.md](internal/architecture.md) — アーキテクチャ概要
- [json-data-model.md](internal/json-data-model.md) — JSON データモデル（定義・マージ戦略・予約プレフィックス）
- [pipeline.md](internal/pipeline/pipeline.md) — パイプライン構成、プロセス連携、AtomicDirWriter
- [SchemaInspector](internal/components/schema-inspector.md)、[Normalizer](internal/components/normalizer.md)、[Composer](internal/components/composer.md)、[Generator](internal/components/generator.md)、[Renderer](internal/components/renderer.md)

## dev

開発環境セットアップ・ツール設定。

- [setup.md](dev/setup.md) — セットアップ手順
- [environment.md](dev/environment.md) — 開発環境定義（DevContainer・VSCode・MCP・.gitignore）
- [checks.md](dev/checks.md) — 開発チェック（IDE・Git hook・CI）

## 開発規約

[DEVELOPMENT.md](../../DEVELOPMENT.md) に統合済み。
