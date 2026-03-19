# Roadmap

## 現行版

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
- ~~2-7. 2-4〜2-6 のコードを削除~~ → 次期版で Python に移行するため不要

## 次期版

設計詳細: [docs/internal/architecture.md](../internal/architecture.md)

実装言語: **Python**

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
- [ ] 3-5. `normalizedSchemaDir` / `normalizedContentsDir` への出力

### Phase 4: Composer

- [ ] 4-1. YAML DSL の設計と実装（from / join / where / group_by / select / sort、LEFT JOIN デフォルト）
- [ ] 4-2. `queriesDir` 評価 → `viewsDir` 生成（パススルークエリ含む）
- [ ] 4-3. 標準クエリ定義（ER図、DFD、CRUDマトリクス）
- [ ] 4-4. ファイル監視（各入力ディレクトリ → Normalizer（3回）、`normalizedContentsDir` + `normalizedQueriesDir` → Composer、`viewsDir` + `templatesDir` + `profilesFile` → Document Generator）

### 将来

- MCP サーバ対応（AI へのコンテキスト提供: validate 結果、DSL 仕様、schema 要約、生成結果確認）
- クエリ可視化テンプレート（Access Query Design View 相当）
- 多言語スキーマ生成（Pydantic ↔ JSON Schema）
- FP 法計測の自動化（要件定義ユースケース向け）
