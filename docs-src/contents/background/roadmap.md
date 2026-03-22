# Roadmap

### Phase 1: 移行準備

- [x] 1-1. TypeScript 実装から未ドキュメントの仕様を救出・ドキュメント化
- [x] 1-2. example-project/output/docs を gitignore 外して commit（現行出力を期待値として保存）
- [x] 1-3. TypeScript コード・設定を削除

### Phase 2: Python 環境構築 + プロジェクト設定

- [x] 2-1. Python 環境構築（DevContainer, VSCode 拡張, MCP 設定）
- [x] 2-2. プロジェクト設定（uv init, CI, ツール導入・配線）

### Phase 3: パススルーパイプライン（自己ドッグフーディング開始）

- [x] 3-1. build コマンド（`<projectDir>/contents/` → `.reqs-builder/<projectDir>/output/` にコピー）
- [x] 3-2. dev コマンド（build + ファイル監視で自動再実行）
- [x] 3-3. docs/ を docs-src/contents/ に移行、参照先を .reqs-builder/docs-src/output/ に変更

### Phase 4: Hugo 連携

- [x] 4-1. Renderer として Hugo を組み込み、dev コマンドで HTML プレビュー

### Phase 5: example-project 同等機能

コンポーネント境界（Generator → Normalizer → Composer）の順に実装。Phase 1 で保存した出力を期待値として使用。

- [x] 5-1. AtomicDirWriter（atomic output: tmpDir 書き出し → rename、version.json、lock）+ パススルーに組み込み
- [ ] 5-2. Watcher をパイプライン基盤に載せ替え（docs-src の既存挙動を維持）
- [ ] 5-3. Generator コア（definition/ 有無でパイプライン分岐、views 読み込み・マージ、Jinja2 + {% section %} インライン展開）
- [ ] 5-4. Normalizer スケルトン（パススルー、検証・正規化は Phase 6）
- [ ] 5-5. Composer スケルトン（パススルー、YAML DSL クエリ評価は Phase 6）

### Phase 6: メタドキュメンテーション前提機能

- [ ] JSON Schema によるスキーマ検証
- [ ] 辞書→配列の正規化（additionalProperties パターン、再帰的）
- [ ] YAML DSL クエリ評価（from / join / where / group_by / select / sort）

### Phase 7: メタドキュメンテーション

スキーマ・クエリの可視化（[meta-documentation.md](../external/app/meta-documentation.md)）。ツール内蔵のスキーマ・クエリ・テンプレートでユーザ定義を可視化する。

### Phase 8: 追加機能（欲しい順）

優先順位はその時点の必要性で決定。

- [ ] Markdown パーサー（データソースとしての Markdown 読み込み）
- [ ] 参照整合性チェック（references.yaml、`--strict`）
- [ ] 標準テンプレート（ER図、DFD、CRUD マトリクス）
- [ ] MCP サーバ対応（AI へのコンテキスト提供: validate 結果、DSL 仕様、schema 要約、生成結果確認）
- [ ] 計算機能プラグインのインターフェース検討（例: ファンクションポイント算出プラグイン）
