# Development Guide

## Conventions (Must Read)

### 開発ワークフロー

各タスクは「1タスク・1 Git ブランチ・1 Claude Code セッション」で進める。

タスク開始時に `npm run ci` を実行し、開発環境・既存コード双方が正常な状態であることを確認する。失敗する場合は、環境の問題であればセットアップの節を、コードの問題であればタスク着手前に修正する。

#### Git

- コミットメッセージ: **英語**
- プルリクエスト タイトル / 本文: **英語**

### セットアップ

#### DevContainer（推奨）

VS Code + DevContainer で即座に開発可能。

1. VS Code で Remote - Containers 拡張をインストール
2. リポジトリを開き「Reopen in Container」を実行
3. コンテナ起動後、確認コマンドを実行（後述）

DevContainer には以下が含まれる:

- Node.js 24 + TypeScript
- GitHub CLI
- Go（MCP Language Server 用）
- uv（将来の Python 移行用）
- Claude Code, ESLint, Prettier 等の VS Code 拡張

#### ローカルセットアップ

DevContainer を使わない場合、上記「DevContainer」節に記載されたツール群をローカルにインストールする。

### 設計工程

- ドキュメント: **日本語**

#### docs/background/ — Why

製品ビジョン、経緯、ロードマップ。読者は開発チーム。

#### docs/external/ — What

ユーザ向け外部仕様。将来そのままユーザドキュメントに昇格させる前提で、利用者視点の振る舞いのみを記述する。内部実装の詳細は書かない。

#### docs/internal/ — How

内部設計・実装仕様。読者は開発者。コンポーネントの処理フロー、プロセス間連携、技術選定等。

#### 設計判断の理由はインラインで残す

設計判断の背景・理由は、判断が書かれている仕様書に「## 背景: ...」セクションとして直接書く。ADR（Architecture Decision Record）のように別ファイルに分離しない。

理由: 仕様と理由が同じファイルにあれば、仕様の変更時に理由も自然に目に入り、更新漏れが起きにくい。別ファイルに分離すると同期コストが発生し、仕様変更で不要になった ADR の削除・更新が漏れやすい。判断数が増えて仕様書が肥大化した場合に ADR 分離を再検討する。

#### ドキュメントの追加・削除時のアクセスパス確認

ドキュメントを追加・削除・移動した場合、プルリクを上げる前に以下のインデックスからのリンクを確認・更新する:

- [docs/index.md](docs/index.md) — 全体インデックス
- [docs/external/index.md](docs/external/index.md) — 外部仕様インデックス
- [DEVELOPMENT.md](DEVELOPMENT.md) — 開発者向けポインタ

### 実装工程

- コード内コメント: **英語**

#### コードスタイル

- **関数型スタイルを優先**: `let` + `for` ループより `map/filter/reduce` を使う
- **命名はモジュール名に合わせる**: `source` モジュールなら `isSourceFile`, `buildSource`
- **関数の並び順（Newspaper style）**: 公開API を先頭に、ヘルパー関数を後に配置。ヘルパーはパイプラインの順序に沿って配置

#### テスト

- **対象**: `src/core/` 配下のビジネスロジック（`src/cli.ts`, `src/commands/` は対象外）
- **カバレッジ目標**: 85%以上
- **アプローチ**: テストファースト（TDD）
- **フィクスチャ**: ファイルベース、モジュール隣接型（`source.fixtures/`）。期待値はテストコード内に記述

#### タスクの進め方

1. **example-project に入出力例を作成** - 具体的な入力と期待出力で仕様を合意
2. **単体テストを記述** - 期待する振る舞いをテストコードで表現
3. **実装してテストをパス**
4. **example-project で動作確認**
5. **`npm run ci`** を実行してからコミット（format, lint, secretlint, build, test:coverage）
6. 完了したらチェックを入れてプルリクを作成

## Documentation (Reference)

- [docs/](docs/index.md) — 仕様・設計
- [docs/background/product.md](docs/background/product.md) — 製品ビジョン
- [docs/internal/architecture.md](docs/internal/architecture.md) — アーキテクチャ
- [docs/background/roadmap.md](docs/background/roadmap.md) — ロードマップ
