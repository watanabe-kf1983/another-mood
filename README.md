# Structured Document Generator

任意の関連オブジェクト群から整合性の取れた構造的ドキュメントを生成する汎用ツール。

## 特徴

- **スキーマ駆動**: OpenAPI/JSON Schema ベースでオブジェクト構造を定義
- **参照整合性チェック**: FK制約相当の検証を自動実行
- **複数形式対応**: Markdown, Mermaid, PlantUML, AsciiDoc
- **Git フレンドリー**: 全てのメタデータは YAML でバージョン管理可能

## ユースケース

- 要件定義書（ERD, DFD, CRUD マトリクス）
- API ドキュメント
- システム設計書
- その他、構造化されたデータから生成できるドキュメント全般

## ステータス

設計フェーズ

## ドキュメント

- [DEVELOPMENT.md](DEVELOPMENT.md) — 開発者向けガイド（セットアップ・規約・パッケージ構成）
- [showcase/examples/ecommerce](showcase/examples/ecommerce/) — ER 図・リレーションのサンプル

## ライセンス

MIT
