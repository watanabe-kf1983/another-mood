# MCP Server Design

MCP サーバの設計。AI へのコンテキスト提供として機能する。

## 基本方針

MCP サーバは CRUD API ではなく、**AI へのコンテキスト提供**として機能する。

data/ の作成・更新・削除（CUD）は AI が直接ファイルを編集する。ツール側で CRUD API を提供しない理由:
- JSON Schema の構造に対する CRUD API（`AppendAdditionalProperty` 等）は設計が膨大になる
- AI は JSON Schema の書き方を既に知っており、YAML ファイルを直接編集できる
- ツールは YAML を読むだけでよいため、ラウンドトリップ保持（ruamel.yaml 等）が不要

## 提供する機能

- **validate の実行と結果返却**: Normalizer を実行し、検証結果・警告を AI に伝える
- **DSL 仕様の提供**: queries/ の YAML DSL の書き方を AI に教える
- **schema/ + references.yaml の要約提供**: AI がデータ編集時に参照関係を理解できるようにする
- **生成結果の確認**: Document Generator が出力した Markdown を AI に見せる

AI にとっての「ドキュメント生成パイプライン全体のナビゲーター」。データの読み書きはしないが、やり方を教えてくれる存在。

## 導入効果

ユーザは MCP サーバをインストールするだけで、CLAUDE.md の設定やフック設定なしに AI がツールを理解して使えるようになる。

## 提供形式

同一機能を2つのインターフェースで提供:

- **CLI**: 人間向け、シェルスクリプト連携用
- **MCP サーバ**: AI エージェント向け（ツール定義が構造化されて提供される）

CLI のみだと AI は使い方を README や --help から推測する必要がある。MCP はツールの引数・型・説明が構造化されており、AI が迷わず使える。
