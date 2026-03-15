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
- [app/](external/app/) — 設定、MCP、メタドキュメンテーション

## [internal/](internal/)

内部設計・実装仕様。

- [architecture.md](internal/architecture.md) — アーキテクチャ概要
- [normalizer.md](internal/normalizer.md) — Normalizer 処理フロー・技術選定
- [composer.md](internal/composer.md) — Composer 処理フロー
- [generator.md](internal/generator.md) — Generator 処理フロー・技術選定
- [renderer.md](internal/renderer.md) — Renderer 処理・構成
- [process-coordination.md](internal/process-coordination.md) — プロセス間連携仕様
- [glossary.md](internal/glossary.md) — 用語集（JSON データモデル等）

## [conventions/](conventions/)

開発規約。

- [design.md](conventions/design.md) — 設計工程（ドキュメント構成、ADR方針）
- [implementation.md](conventions/implementation.md) — 実装工程（コード規約、テスト規約）
- [workflow.md](conventions/workflow.md) — 工程共通（タスクの進め方、Git運用、言語）
