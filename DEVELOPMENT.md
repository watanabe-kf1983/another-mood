# Development Guide

## Conventions (Must Read)

### 開発ワークフロー

各タスクは「1タスク・1 Git ブランチ・1 Claude Code セッション」で進める。

タスク開始時に `make ci` を実行し、開発環境・既存コード双方が正常な状態であることを確認する。失敗する場合は、環境の問題であればセットアップの節を、コードの問題であればタスク着手前に修正する。

#### Git

- コミットメッセージ: **英語**
- プルリクエスト タイトル / 本文: **英語**

### セットアップ

ツールの動作には [uv](https://docs.astral.sh/uv/) が必要。インストール後 `uv sync` で依存を解決する。

このプロジェクト自身が Another Mood でドキュメントを管理している。開発者向け設計書は `dev-docs/`、利用者向けサンプルプロジェクト群は `showcase/`（user-guide / starter / examples）にある。それぞれを以下のコマンドでビルドする:

```bash
mood build dev-docs
mood build showcase/examples/ecommerce
```

出力は `.another-mood/{project}/output/` に書き出される。起点は [.another-mood/dev-docs/output/reports/prose/index.md](.another-mood/dev-docs/output/reports/prose/index.md)。

ソース編集中は `mood watch dev-docs` で自動リビルドできる。ただし Another Mood 本体（Python コード）を変更する場合は古いコードで watch が動き続けるため、つど `mood build dev-docs` を再実行する。

タスク開始時には `mood build dev-docs` でドキュメントをビルドし、仕様が参照できる状態にする。

### 設計工程

- ドキュメント: **日本語**
- 設計ソース: `dev-docs/contents/` 配下の 3 カテゴリ（background / design / internal）

設計ドキュメントの変更は、必ず `dev-docs/contents/` 配下のソースに対して行い、変更後は `mood build dev-docs` を実行して `.another-mood/dev-docs/output/` の出力を確認する。

#### background/ — Why

製品ビジョン、経緯、ロードマップ。読者は開発チーム。

#### design/ — What

利用者視点の振る舞い仕様。設計工程の作業場として TOBE や検討中の方針も書き残す。実装済みのものは `docs/` 側に利用者向けリファレンスとして整理する（将来 `showcase/user-guide/` へ構造化移植予定）。

#### internal/ — How

内部設計・実装仕様。読者は開発者。コンポーネントの処理フロー、プロセス間連携、技術選定等。設計フェーズの作業場であり、実装完了後は実装工程の規約に従い整理する。

設計フェーズの作業場という性質上、まだ実装されていない検討中の方針や TOBE 像が場当たり的に書き残されていることがある。実装方針を検討する際は、現在のコード（How）と internal/（Why / TOBE）をペアで参照すること。コードだけ見ると過去の議論で既に到達済みの結論を再発明する恐れがある。

#### 設計判断の理由はインラインで残す

設計判断の背景・理由は、判断が書かれている仕様書に「## 背景: ...」セクションとして直接書く。ADR（Architecture Decision Record）のように別ファイルに分離しない。

理由: 仕様と理由が同じファイルにあれば、仕様の変更時に理由も自然に目に入り、更新漏れが起きにくい。別ファイルに分離すると同期コストが発生し、仕様変更で不要になった ADR の削除・更新が漏れやすい。判断数が増えて仕様書が肥大化した場合に ADR 分離を再検討する。

#### ドキュメントの追加・削除時のアクセスパス確認

ドキュメントを追加・削除・移動した場合、プルリクを上げる前に以下のインデックスからのリンクを確認・更新する:

- [index.md](.another-mood/dev-docs/output/reports/prose/index.md) — 全体インデックス
- [design/index.md](.another-mood/dev-docs/output/reports/prose/design/index.md) — 設計仕様インデックス
- [DEVELOPMENT.md](DEVELOPMENT.md) — 開発者向けポインタ

### 実装工程

- コード内コメント: **英語**

#### ライブラリ選定

ライブラリ導入は、常にその時点での有力なものを比較検討したうえで決定する。**選定理由は、そのライブラリを使っているコンポーネントの internal/ 設計書に「## 背景: ...」セクションとしてインラインで残す**。コミットメッセージだけでは将来の再検討時に発掘コストが高い。

#### パッケージ構成と依存ルール

```
another_mood/
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

- **カバレッジ計測対象**: `components/`。目標は Statements + Branches トータルで 90%以上
- **フィクスチャ**: ファイルベース、モジュール隣接型。期待値はテストコード内に記述

#### internal/ ドキュメントの整理

internal/ ドキュメントは実装中は参照するため残し、全テスト green 後の最終整理として行う。コードから読み取れる内容（フロー、データ構造等）は削除し、設計判断の背景（Why）はコードの docstring やコミットメッセージに移す。

#### 利用者向けドキュメント

`docs/`（素 Markdown、英語）。実装が完了した機能から書く。`docs/` には Implemented 機能のみ記載する方針に従う。B/C/E3 完了後に `showcase/user-guide/` へ構造化移植予定。

執筆スタイル: 文体は簡潔な英語。ただし「簡潔さ」は装飾・冗長表現を削ぐ意味であり、説明の正確さ・網羅性・分かりやすさは妥協しない（MCP 経由で LLM が docs/ を読む際の UX に直結するため）。

#### タスクの進め方

1. **showcase/examples/ のいずれかに入出力例を作成** - 具体的な入力と期待出力で仕様を合意
2. **単体テストを記述** - 期待する振る舞いをテストコードで表現
3. **実装してテストをパス**
4. **showcase/ のサンプルで動作確認**
5. **ユーザに見える挙動が変わった場合は `docs/` を同期** - CLI / スキーマ / クエリ / テンプレートの仕様や挙動を変えた、機能を追加・削除した、内蔵リソース（`src/another_mood/resources/schemas/*.yaml` 等）を改変した場合は、対応する `docs/reference/` 各章および必要に応じて `docs/guides.md` を更新する。`docs/` は Implemented 機能のみを記載するという方針に従う
6. `make ci` を実行してからコミット
7. 完了したらチェックを入れてプルリクを作成

## Documentation (Reference)

ドキュメントの閲覧先は `.another-mood/dev-docs/output/`（ビルド方法はセットアップの節を参照）。

- [index.md](.another-mood/dev-docs/output/reports/prose/index.md) — 仕様・設計
- [background/product.md](.another-mood/dev-docs/output/reports/prose/background/product.md) — 製品ビジョン
- [internal/architecture.md](.another-mood/dev-docs/output/reports/prose/internal/architecture.md) — アーキテクチャ
- [roadmap.md](.another-mood/dev-docs/output/reports/roadmap.md) — ロードマップ（Phase 8 以降）
- [tasks.md](.another-mood/dev-docs/output/reports/tasks.md) — タスクカタログ（機能カテゴリ別）
- [dev/style-guide.md](.another-mood/dev-docs/output/reports/prose/dev/style-guide.md) — 命名・自己定義の表記規約
