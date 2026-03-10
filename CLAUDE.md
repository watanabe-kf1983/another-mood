# Structured Document Generator

## Overview

任意の関連するオブジェクト群とドキュメントテンプレートから、整合性の取れた構造的ドキュメントを生成する汎用ツール。

- 製品ビジョン: [docs/internal/product.md](docs/internal/product.md)
- アーキテクチャ: [docs/internal/architecture.md](docs/internal/architecture.md)

## Technical Stack

- **言語: TypeScript**
- ランタイム: Node.js
- スキーマ検証: Zod
- YAML 処理: js-yaml
- テンプレート: LiquidJS
- クエリ: jsonpath-plus
- ディレクトリハッシュ: folder-hash
- ファイル監視: chokidar
- ドキュメントレンダリング: Hugo (hugo-bin 経由)

### TypeScript を選択した理由

- **MCP 配布が容易**: `npx reqs-builder` で即実行、pip + 仮想環境の説明不要
- **エコシステム**: chokidar, folder-hash 等の監視・ハッシュ系ライブラリが成熟
- **単一パッケージで CLI + MCP**: Node の `bin` フィールドで CLI、MCP SDK も npm で導入可能
- **AI との協調**: 型定義が「仕様書」として機能し、Claude Code がコードの意図を理解しやすい

### LiquidJS を選択した理由

- **フィルタの充実**: `map`, `uniq`, `where` 等のフィルタが標準で利用可能
- **Shopify Liquid 互換**: 広く使われている Shopify テーマの記法と互換性があり、ドキュメントやサンプルが豊富
- **11ty との親和性**: 11ty は LiquidJS をネイティブサポートしており、統合が容易

### Hugo を選択した理由

- **Node.js で完結**: hugo-bin により `npm install` 時にバイナリ自動取得、Python/Ruby 不要
- **高速**: Go 製シングルバイナリ、大量ファイルでも高速ビルド
- **ライブリロード**: `hugo server` で変更を即座にブラウザ反映
- **静的エクスポート**: `hugo` コマンドで HTML 一式を出力、ポータブルに配布可能
- **Mermaid 対応**: ER図、シーケンス図、フローチャート等を描画可能
- **将来**: AsciiDoc レンダリング環境への差し替えも検討（Asciidoctor.js または外部サーバ連携）

### 図表記の方針

- 基本: Mermaid（ER図、シーケンス図、フローチャート等）
- Mermaid 非対応の図（ユースケース図等）は代替記法で対応
- 将来: PlantUML 対応を検討（Java 依存のため優先度低）

## Project Structure

### アプリケーション構成

```
reqs-builder/
  package.json
  tsconfig.json
  src/
    cli.ts                # エントリポイント
    commands/
      validate.ts         # reqs-builder validate
      generate.ts         # reqs-builder generate
      dev.ts              # reqs-builder dev (統合起動)
      mcp-server.ts       # reqs-builder mcp-server（将来）
    core/
      hash.ts             # ディレクトリハッシュ計算
      source.ts           # ソースYAML読み込み・マージ
      schema-validator.ts # 参照整合性チェック
      toc.ts              # toc定義の読み込み・展開
      template-expander.ts # テンプレート展開
  resources/              # 静的リソース（アプリ同梱）
    hugo/                 # Hugo 関連
      hugo.toml           # Hugo 設定
      layouts/            # Hugo レイアウト
    (将来) templates/     # 標準テンプレート
      er.md               # Mermaid ER図
      dfd.md              # DFD
```

### ユーザプロジェクト構成（例）

```
my-project/
  schema/                 # スキーマ定義
    entities.yaml
    relations.yaml
  source/                 # ソースデータ
    entities/
      user.yaml
      order.yaml
    relations.yaml
  toc/                    # 目次定義（ドキュメント単位の導出）
    erds.yaml.liquid
    entities.yaml.liquid
  templates/              # ユーザ定義テンプレート（オーバーライド用）
    entities-chapter.md
  output/                 # 出力先（生成される）
    docs/                 # Generator が生成した Markdown
      system-overview.md
      entities.md
```

## Specifications

### アプリケーション仕様（テストの入力）

- 設定システム: [docs/specs/config.spec.md](docs/specs/config.spec.md)
- Markdownパーサー: [docs/specs/markdown-parser.spec.md](docs/specs/markdown-parser.spec.md)

### ユーザ向けファイルフォーマット仕様

- スキーマ定義: [docs/user-guide/schema-spec.md](docs/user-guide/schema-spec.md)
- ToC 仕様: [docs/user-guide/toc-spec.md](docs/user-guide/toc-spec.md)
- テンプレート仕様: [docs/user-guide/template-spec.md](docs/user-guide/template-spec.md)
- API設計（将来）: [docs/user-guide/api-design.md](docs/user-guide/api-design.md)

## Development

### コード規約

#### スタイル

- **関数型スタイルを優先**: `let` + `for` ループより `map/filter/reduce` を使う
- **命名はモジュール名に合わせる**: `source` モジュールなら `isSourceFile`, `buildSource`
- **関数の並び順（Newspaper style）**: 公開API を先頭に、ヘルパー関数を後に配置。ヘルパーはパイプラインの順序に沿って配置

#### テスト

- **対象**: `src/core/` 配下のビジネスロジック（`src/cli.ts`, `src/commands/` は対象外）
- **カバレッジ目標**: 85%以上
- **アプローチ**: テストファースト（TDD）
- **フィクスチャ**: ファイルベース、モジュール隣接型（`source.fixtures/`）。期待値はテストコード内に記述

#### 言語

- **コード内コメント / コミットメッセージ / プルリクエスト**: 英語
- **ドキュメント（CLAUDE.md 等）**: 日本語

### 開発ワークフロー

各タスクは「1タスク・1 Git ブランチ・1 Claude Code セッション」で進める。

タスク内の進め方:

1. **example-project に入出力例を作成** - 具体的な入力と期待出力で仕様を合意
2. **単体テストを記述** - 期待する振る舞いをテストコードで表現
3. **実装してテストをパス**
4. **example-project で動作確認**
5. **`npm run ci`** を実行してからコミット（format, lint, secretlint, build, test:coverage）
6. 完了したらチェックを入れてプルリクを作成

### 設計判断

1. **既存ツールを最大限活用** - 車輪の再発明を避ける
2. **スキーマ定義は言語非依存な資産** - YAML/JSON Schema として Git 管理
3. **周辺ツールは差し替え可能に** - 出力形式、レンダリングツール等は疎結合に
4. **クエリは YAML DSL** - クエリ自体が構造化データ、ツール自身で管理・可視化可能
5. **CUD は AI 直接編集** - ツールは YAML を読むだけ、CRUD API は提供しない
6. **スキーマは JSON Schema** - 独自形式を避け、additionalProperties で辞書→配列の正規化を行う

### Roadmap

#### Phase 1: 出力確認環境

- [x] 1-1. 統合起動コマンドの作成（reqs-builder dev）
- [x] 1-2. Hugo セットアップ (hugo-bin)

#### Phase 2: Generator

- [x] 2-1. GitHub Actions 導入（テスト・カバレッジ必須化、main保護）
- [x] 2-2. テンプレートエンジン + データYAML読み込み + generate コマンド
- [x] 2-3. ファイル監視機能の追加
- [x] 2-4. pagination（複数ファイル生成）
- [x] 2-5. toc 定義の読み込み（ToC テンプレート）
- [x] 2-6. テンプレートエンジンを LiquidJS へ移行
- [ ] 2-7. 2-4〜2-6 のコードを削除（pagination, toc, LiquidJS 移行を revert し 2-3 の状態に戻す）

### Roadmap（次期版）

設計詳細: [docs/internal/toc-redesign.md](docs/internal/toc-redesign.md)

実装言語は未定（Python or TypeScript）。

#### Phase 1: 出力確認環境

- [ ] 1-1. プロジェクトセットアップ（テストフレームワーク、リンター、DevContainer）
- [ ] 1-2. Hugo セットアップ + dev コマンド（統合起動）

#### Phase 2: Document Generator

- [ ] 2-1. GitHub Actions 導入（テスト・カバレッジ必須化、main保護）
- [ ] 2-2. ソース YAML 読み込み + テンプレート展開 + generate コマンド
- [ ] 2-3. ファイル監視
- [ ] 2-4. フラットアンカーマップ構築（`key` 持ちオブジェクトから ID 自動生成）
- [ ] 2-5. paging 設定（クラス → ファイルパスのマッピング、プロファイル切り替え）
- [ ] 2-6. `{% section %}` カスタムタグ（paging に応じた分割 / インライン展開）
- [ ] 2-7. リンク解決（`link_md` フィルタ、Markdown 内 `toc:id` 記法）
- [ ] 2-8. エスケープ基盤（Markdown / Mermaid、パーシャル拡張子で判定）
- [ ] 2-9. Markdownパーサー（データソースとしてのMarkdown読み込み）
- [ ] 2-10. 標準ドキュメントテンプレート（ER図、DFD、CRUDマトリクス）

#### Phase 3: Validator

- [ ] 3-1. schema/ の JSON Schema 検証
- [ ] 3-2. source/ の型検証 + 参照整合性チェック（FK 制約）
- [ ] 3-3. 正規化（additionalProperties パターンの辞書→配列変換）
- [ ] 3-4. 検証結果の出力

#### Phase 4: Preparer

- [ ] 4-1. YAML DSL の設計と実装（from / join / where / group_by / select / sort）
- [ ] 4-2. queries/ 評価 → output/prepared/ 生成
- [ ] 4-3. 標準クエリ定義（ER図、DFD、CRUDマトリクス）
- [ ] 4-4. ファイル監視（schema/ + source/ + queries/ → Validator + Preparer、prepared/ + templates/ + paging/ → Document Generator）

#### 将来

- MCP サーバ対応（Validate + Query の提供。CUD は AI が直接ファイル編集）
- クエリ可視化テンプレート（Access Query Design View 相当）
- 多言語スキーマ生成（Pydantic ↔ Zod）
- FP 法計測の自動化（要件定義ユースケース向け）
