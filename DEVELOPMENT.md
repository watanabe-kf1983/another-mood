# Development Guide

## Documentation

詳細は [docs/](docs/index.md) を参照。

- 製品ビジョン: [docs/background/product.md](docs/background/product.md)
- アーキテクチャ: [docs/internal/architecture.md](docs/internal/architecture.md)
- 再設計の経緯: [docs/background/toc-redesign.md](docs/background/toc-redesign.md)

## Technical Stack（現行 TypeScript 実装）

- **言語: TypeScript**（次期版の言語は未定: Python or TypeScript）
- ランタイム: Node.js
- スキーマ検証: Zod
- YAML 処理: js-yaml
- テンプレート: LiquidJS
- ディレクトリハッシュ: folder-hash
- ファイル監視: chokidar
- ドキュメントレンダリング: Hugo (hugo-bin 経由)

技術選定の理由は [docs/internal/](docs/internal/) 内の各コンポーネントファイルを参照。

## コード規約

### スタイル

- **関数型スタイルを優先**: `let` + `for` ループより `map/filter/reduce` を使う
- **命名はモジュール名に合わせる**: `source` モジュールなら `isSourceFile`, `buildSource`
- **関数の並び順（Newspaper style）**: 公開API を先頭に、ヘルパー関数を後に配置。ヘルパーはパイプラインの順序に沿って配置

### テスト

- **対象**: `src/core/` 配下のビジネスロジック（`src/cli.ts`, `src/commands/` は対象外）
- **カバレッジ目標**: 85%以上
- **アプローチ**: テストファースト（TDD）
- **フィクスチャ**: ファイルベース、モジュール隣接型（`source.fixtures/`）。期待値はテストコード内に記述

### 言語

- **コード内コメント / コミットメッセージ / プルリクエスト**: 英語
- **ドキュメント（CLAUDE.md 等）**: 日本語

## 開発ワークフロー

各タスクは「1タスク・1 Git ブランチ・1 Claude Code セッション」で進める。

タスク内の進め方:

1. **example-project に入出力例を作成** - 具体的な入力と期待出力で仕様を合意
2. **単体テストを記述** - 期待する振る舞いをテストコードで表現
3. **実装してテストをパス**
4. **example-project で動作確認**
5. **`npm run ci`** を実行してからコミット（format, lint, secretlint, build, test:coverage）
6. 完了したらチェックを入れてプルリクを作成

## 設計判断

1. **既存ツールを最大限活用** - 車輪の再発明を避ける
2. **スキーマ定義は言語非依存な資産** - YAML/JSON Schema として Git 管理
3. **周辺ツールは差し替え可能に** - 出力形式、レンダリングツール等は疎結合に
4. **クエリは YAML DSL** - クエリ自体が構造化データ、ツール自身で管理・可視化可能
5. **CUD は AI 直接編集** - ツールは YAML を読むだけ、CRUD API は提供しない
6. **スキーマは JSON Schema** - 独自形式を避け、additionalProperties で辞書→配列の正規化を行う

## Roadmap（現行版）

### Phase 1: 出力確認環境

- [x] 1-1. 統合起動コマンドの作成（reqs-builder dev）
- [x] 1-2. Hugo セットアップ (hugo-bin)

### Phase 2: Generator

- [x] 2-1. GitHub Actions 導入（テスト・カバレッジ必須化、main保護）
- [x] 2-2. テンプレートエンジン + データYAML読み込み + generate コマンド
- [x] 2-3. ファイル監視機能の追加
- [x] 2-4. pagination（複数ファイル生成）
- [x] 2-5. toc 定義の読み込み（ToC テンプレート）
- [x] 2-6. テンプレートエンジンを LiquidJS へ移行
- [ ] 2-7. 2-4〜2-6 のコードを削除（pagination, toc, LiquidJS 移行を revert し 2-3 の状態に戻す）

## Roadmap（次期版）

設計詳細: [docs/background/toc-redesign.md](docs/background/toc-redesign.md)

実装言語は未定（Python or TypeScript）。

### Phase 1: 出力確認環境

- [ ] 1-1. プロジェクトセットアップ（テストフレームワーク、リンター、DevContainer）
- [ ] 1-2. Hugo セットアップ + dev コマンド（統合起動）

### Phase 2: Document Generator

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

### Phase 3: Normalizer

- [ ] 3-1. schema/ の JSON Schema 検証（トップレベルキー = スキーマ名）
- [ ] 3-2. data/ の型検証
- [ ] 3-3. 参照整合性チェック（references.yaml、`--strict` で警告のみ）
- [ ] 3-4. 正規化（additionalProperties パターンの辞書→配列変換、再帰的）
- [ ] 3-5. output/model/normalized/ への出力

### Phase 4: Composer

- [ ] 4-1. YAML DSL の設計と実装（from / join / where / group_by / select / sort、LEFT JOIN デフォルト）
- [ ] 4-2. queries/ 評価 → output/model/views/ 生成（パススルークエリ含む）
- [ ] 4-3. 標準クエリ定義（ER図、DFD、CRUDマトリクス）
- [ ] 4-4. ファイル監視（schema/ + data/ → Normalizer、normalized/ + queries/ → Composer、views/ + templates/ + paging.yaml → Document Generator）

### 将来

- MCP サーバ対応（AI へのコンテキスト提供: validate 結果、DSL 仕様、schema 要約、生成結果確認）
- クエリ可視化テンプレート（Access Query Design View 相当）
- 多言語スキーマ生成（Pydantic ↔ Zod）
- FP 法計測の自動化（要件定義ユースケース向け）
