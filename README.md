# Another Mood

ドキュメントビルドツール。関連するオブジェクト群（YAML / Markdown）とテンプレートから、整合性の取れた構造的ドキュメントを生成する。

## クイックスタート

```bash
uv sync
uv run mood build showcase/examples/ecommerce
```

出力は `.another-mood/showcase/examples/ecommerce/output/` に書き出される。

## ステータス

開発中（private）。Phase 8 進行中 — [dev-docs/contents/tasks.yaml](dev-docs/contents/tasks.yaml) を参照。Phase 10 完了後に public 化予定。

設計判断と背景は [background/product.md](dev-docs/contents/background/product.md) を参照。

## ドキュメント

- [docs/](docs/) — ユーザガイド *(執筆中)*
- [DEVELOPMENT.md](DEVELOPMENT.md) — 開発者向けガイド
- [showcase/examples/ecommerce/](showcase/examples/ecommerce/) — サンプルプロジェクト
