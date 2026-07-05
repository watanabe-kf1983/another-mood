# Development Guide

## Conventions (Must Read)

### 開発ワークフロー

- 各タスクは「1タスク・1 Git ブランチ・1 Claude Code セッション」で進める
- タスク開始時に `make ci` を実行し、開発環境・既存コードが正常な状態であることを確認する。失敗する場合は、環境の問題ならセットアップ節を、コードの問題ならタスク着手前に修正する
- コミットメッセージ・プルリクエストは **英語**

### セットアップ

ツールの動作には [uv](https://docs.astral.sh/uv/) が必要。インストール後 `uv sync` で依存を解決する。

このプロジェクト自身が Another Mood でドキュメントを管理している。タスク開始時には `mood build dev-docs` でドキュメントをビルドし、仕様が参照できる状態にする。起点は [.another-mood/dev-docs/output/web/index.md](.another-mood/dev-docs/output/web/index.md)。

利用者向けサンプルプロジェクト群は `showcase/`（`starter` / `music` 等の各テンプレート）にある。`mood build showcase/{name}` でビルドできる。

### ドキュメント

ドキュメントは以下の三系統で管理する:

- **`docs/`** — 利用者向けリファレンス（外部仕様の正本）。素 Markdown、英語。実装済み機能のみ。文体は簡潔だが、正確さ・網羅性は妥協しない（MCP 経由で LLM が読む UX に直結するため）
- **`dev-docs/background/`** — 製品ビジョン、ロードマップ、タスクカタログ等の開発判断の根拠。日本語。Another Mood で管理
- **`dev-docs/design/`** — 設計仕様。日本語。各ファイルは以下の 3 セクション構造（該当があるもののみ）:
    - `## External Design` — 利用者から見える振る舞いの設計判断
    - `## Internal Design` — 内部実装の設計判断
    - `## Proposals` — 未実装機能（task に対応）

`Proposals` の検討メモは、実装完了時に削除する（部分実装なら残る検討事項のみに絞る）。維持価値のある設計判断は External / Internal Design 節に移すか、code docstring やコミットメッセージで残す。

設計判断の背景・理由は、判断が書かれている場所に直接書く（ADR のように別ファイルに分離しない）。`design/` 内では「## 背景: ...」セクションとして該当箇所の近傍に書き、実装済み機能ではコードの docstring かコミットメッセージで残す。

理由: 仕様と理由が同じ場所にあれば、仕様の変更時に理由も自然に目に入り、更新漏れが起きにくい。別ファイルに分離すると同期コストが発生し、仕様変更で不要になった ADR の削除・更新が漏れやすい。

ドキュメントを追加・削除・移動した場合、プルリクを上げる前に以下のインデックスからのリンクを確認・更新する:

- [index.md](.another-mood/dev-docs/output/web/index.md) — dev-docs 全体インデックス
- [docs/index.md](docs/index.md) — 利用者向けトップ
- [docs/catalog.yaml](docs/catalog.yaml) — MCP 公開対象のカタログ
- [DEVELOPMENT.md](DEVELOPMENT.md) — 開発者向けポインタ

### 実装

- コード内コメントは **英語**
- ライブラリ導入は、その時点での有力なものを比較検討したうえで決定する。**選定理由はそのライブラリを使うコンポーネントの近傍（`dev-docs/design/` の対応ファイル、実装済みならコードの docstring）に残す**

#### パッケージ構成と依存ルール

```
another_mood/
├── cli.py                  # CLI エントリポイント
├── mcp_server.py           # MCP サーバエントリポイント
├── command.py              # CLI / MCP 共通の操作層（BuildResult 等を返す）
├── config.py               # 設定
├── components/             # ビジネスロジック
│   ├── shared/             #   共通基盤
│   ├── preprocess/         #   入力の正規化・スキーマ解釈・クエリ導出
│   ├── composer/           #   合成: データ + クエリ → ビュー
│   ├── generator/          #   生成: ビュー + テンプレート → Markdown
│   ├── publish/            #   出力の書き出し
│   ├── scaffold/           #   プロジェクト初期化・ブループリント
│   └── docs_catalog/       #   バンドル済みドキュメントの目録
├── pipeline/               # オーケストレーション: ステージ実行
│   └── adapters/           #   外部ツール連携（Hugo, watchfiles）
└── resources/              # 静的リソース
```

依存方向: `{cli, mcp_server}` → `command` → `pipeline` → `components/*` → `components/shared`

#### コードスタイル

- **関数型スタイルを優先**: `for` ループより内包表記、`map/filter` 等。引数・戻り値はイミュータブル型（`dict` → `Mapping`、`list` → `Sequence` 等）
- **`Any` はなるべく使わない**: `object` 等で型安全性を保つ
- **命名はモジュール名に合わせる**: `source` モジュールなら `is_source_file`, `build_source`
- **関数の並び順（Newspaper style）**: 公開 API を先頭、ヘルパーを後ろ。ヘルパーはパイプライン順
- **`@dataclass` は `frozen=True`**: `__init__` ボイラープレート削減目的、immutable がデフォルト
- **制御フローは論理の形に合わせる**: 両枝が対等な結果を返す *対称な分岐* は `if/else`（両枝が `return` でも `else` を畳まない）。前提失敗・エラー・エッジを先頭で剥がす *非対称な bail-out* のみ guard clause（早期 `return`）。`else` とインデントは条件付き領域の境界情報なので、機能的に冗長でも残す（*explicit is better than implicit*）。`else` を機械的に除去させる pylint `no-else-return` / ruff `RET505` は採らない（RET は `select` 外）

#### テスト

- **カバレッジ計測対象**: `components/`。Statements + Branches トータルで 90% 以上
- **フィクスチャ**: ファイルベース、モジュール隣接型。期待値はテストコード内に記述

#### 動作確認 (`mood watch` + Playwright MCP)

`showcase/` や `dev-docs/` のテンプレート変更を実機で確認するときは `mood watch <project_dir> --port <port>` でローカルプレビューを上げ、必要なら Playwright MCP でレンダリングを観る。Playwright MCP の作業ファイルはすべて `.gitignore` 済みの `.playwright-mcp/` 配下に集約する:

- ページスナップショット / console ログは Playwright MCP が自動でこのディレクトリに出す
- スクリーンショットは `browser_take_screenshot` の `filename` に `.playwright-mcp/<name>.png` を指定する (デフォルトは cwd 直下に落ちて散らかる)

検証目的のスクショは再現可能なので、コミット前に削除して構わない。

#### タスクの進め方

非自明な機能追加・変更では、まず `dev-docs/design/` の対応ファイル `## Proposals` セクション（必要なら新規ファイル）に検討メモを書いて方針を合意してから着手する。以降の手順:

1. 以下をタスクに応じた順序で進める:
    - **showcase/ のテンプレートに入出力例を作成**
    - **単体テストを記述**
    - **実装**
2. **showcase/ で動作確認**
3. **`docs/` を同期** — ユーザに見える挙動（CLI / スキーマ / クエリ / テンプレートの仕様、内蔵リソース等）が変わった場合に `docs/reference/` 各章および必要に応じて `docs/guides.md` を更新
4. **`Proposals` の整理** — 対応ファイルの `## Proposals` から該当の検討メモを削除（部分実装の場合は残る検討事項のみに絞る）。維持価値のある設計判断は External / Internal Design 節に移すか、コードの docstring に残す
5. `make ci` を通してコミット → プルリク作成

## Documentation (Reference)

ドキュメントの閲覧先は `.another-mood/dev-docs/output/web/`。

- [index.md](.another-mood/dev-docs/output/web/index.md) — 仕様・設計
- [background/product.md](.another-mood/dev-docs/output/web/prose/10-background/10-product.md) — 製品ビジョン
- [roadmap.md](.another-mood/dev-docs/output/web/roadmap.md) — ロードマップ
- [tasks.md](.another-mood/dev-docs/output/web/tasks.md) — タスクカタログ
- [dev/style-guide.md](.another-mood/dev-docs/output/web/prose/30-dev/40-style-guide.md) — 命名・自己定義の表記規約
