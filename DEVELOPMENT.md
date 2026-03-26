# Development Guide

## Conventions (Must Read)

### 開発ワークフロー

各タスクは「1タスク・1 Git ブランチ・1 Claude Code セッション」で進める。

タスク開始時に `make ci` を実行し、開発環境・既存コード双方が正常な状態であることを確認する。失敗する場合は、環境の問題であればセットアップの節を、コードの問題であればタスク着手前に修正する。

#### Git

- コミットメッセージ: **英語**
- プルリクエスト タイトル / 本文: **英語**

### セットアップ

開発環境・ドキュメントの構築手順は [docs/README.md](docs/README.md) を参照。

タスク開始時には `reqs build docs-src` でドキュメントをビルドし、仕様が参照できる状態にする。

### 設計工程

- ドキュメント: **日本語**
- ドキュメントソース: `docs-src/contents/` 配下の 3 カテゴリ

設計ドキュメントの変更は、必ず `docs-src/contents/` 配下のソースに対して行い、変更後は `reqs build docs-src` を実行して `.reqs-builder/docs-src/output/` の出力を確認する。

#### background/ — Why

製品ビジョン、経緯、ロードマップ。読者は開発チーム。

#### external/ — What

ユーザ向け外部仕様。将来そのままユーザドキュメントに昇格させる前提で、利用者視点の振る舞いのみを記述する。内部実装の詳細は書かない。

#### internal/ — How

内部設計・実装仕様。読者は開発者。コンポーネントの処理フロー、プロセス間連携、技術選定等。設計フェーズの作業場であり、実装完了後は実装工程の規約に従い整理する。

#### 設計判断の理由はインラインで残す

設計判断の背景・理由は、判断が書かれている仕様書に「## 背景: ...」セクションとして直接書く。ADR（Architecture Decision Record）のように別ファイルに分離しない。

理由: 仕様と理由が同じファイルにあれば、仕様の変更時に理由も自然に目に入り、更新漏れが起きにくい。別ファイルに分離すると同期コストが発生し、仕様変更で不要になった ADR の削除・更新が漏れやすい。判断数が増えて仕様書が肥大化した場合に ADR 分離を再検討する。

#### ドキュメントの追加・削除時のアクセスパス確認

ドキュメントを追加・削除・移動した場合、プルリクを上げる前に以下のインデックスからのリンクを確認・更新する:

- [index.md](.reqs-builder/docs-src/output/prose/index.md) — 全体インデックス
- [external/index.md](.reqs-builder/docs-src/output/prose/external/index.md) — 外部仕様インデックス
- [DEVELOPMENT.md](DEVELOPMENT.md) — 開発者向けポインタ

### 実装工程

- コード内コメント: **英語**

#### ライブラリ選定

ライブラリ導入は、常にその時点での有力なものを比較検討したうえで決定する。

#### パッケージ構成と依存ルール

```
reqs_builder/
├── cli.py                  # Main: エントリポイント、依存の組み立て
├── config.py               # 設定
├── components/             # ビジネスロジック
│   ├── shared/             #   共通基盤（json_data_model, yaml_dumper）
│   ├── normalizer/         #   正規化: Markdown → YAML
│   ├── composer/            #   合成: 正規化データ + クエリ → ビュー
│   └── generator/          #   生成: ビュー + テンプレート → Markdown
├── pipeline/               # オーケストレーション: ステージ実行・監視
│   └── adapters/           #   外部ツール連携（Hugo, watchfiles）
└── resources/              # 静的リソース
```

依存ルール:

- `cli` → `pipeline` → `components/*` → `components/shared`

#### コードスタイル

- **関数型スタイルを優先**: `for` ループより内包表記、`map/filter` 等を使う。関数の引数・戻り値はイミュータブルな型を使う（`dict` → `Mapping`、`list` → `Sequence` 等）
- **`Any` はなるべく使わない**: `object` 等で型安全性を保つ
- **命名はモジュール名に合わせる**: `source` モジュールなら `is_source_file`, `build_source`
- **関数の並び順（Newspaper style）**: 公開API を先頭に、ヘルパー関数を後に配置。ヘルパーはパイプラインの順序に沿って配置
- **`@dataclass` は `frozen=True` で使う**: `__init__` ボイラープレートの削減が目的。immutable がデフォルト

#### テスト

- **対象**: ビジネスロジック（CLI エントリポイントは対象外）
- **カバレッジ目標**: Statements + Branches トータルで 90%以上
- **フィクスチャ**: ファイルベース、モジュール隣接型。期待値はテストコード内に記述

#### internal/ ドキュメントの整理

internal/ ドキュメントは実装中は参照するため残し、全テスト green 後の最終整理として行う。コードから読み取れる内容（フロー、データ構造等）は削除し、設計判断の背景（Why）はコードの docstring やコミットメッセージに移す。

#### タスクの進め方

1. **example-project に入出力例を作成** - 具体的な入力と期待出力で仕様を合意
2. **単体テストを記述** - 期待する振る舞いをテストコードで表現
3. **実装してテストをパス**
4. **example-project で動作確認**
5. `make ci` を実行してからコミット
6. 完了したらチェックを入れてプルリクを作成

## Documentation (Reference)

ドキュメントの閲覧先は `.reqs-builder/docs-src/output/`（ビルド方法は [docs/README.md](docs/README.md) を参照）。

- [index.md](.reqs-builder/docs-src/output/prose/index.md) — 仕様・設計
- [background/product.md](.reqs-builder/docs-src/output/prose/background/product.md) — 製品ビジョン
- [internal/architecture.md](.reqs-builder/docs-src/output/prose/internal/architecture.md) — アーキテクチャ
- [background/roadmap.md](.reqs-builder/docs-src/output/prose/background/roadmap.md) — ロードマップ
