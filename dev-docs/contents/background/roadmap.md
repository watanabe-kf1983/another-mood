# Roadmap

### Phase 1: 移行準備

- [x] 1-1. TypeScript 実装から未ドキュメントの仕様を救出・ドキュメント化
- [x] 1-2. example-project/output/docs を gitignore 外して commit（現行出力を期待値として保存）
- [x] 1-3. TypeScript コード・設定を削除

### Phase 2: Python 環境構築 + プロジェクト設定

- [x] 2-1. Python 環境構築（DevContainer, VSCode 拡張, MCP 設定）
- [x] 2-2. プロジェクト設定（uv init, CI, ツール導入・配線）

### Phase 3: パススルーパイプライン（自己ドッグフーディング開始）

- [x] 3-1. build コマンド（`<projectDir>/contents/` → `.another-mood/<projectDir>/output/` にコピー）
- [x] 3-2. dev コマンド（build + ファイル監視で自動再実行）
- [x] 3-3. docs/ を docs-src/contents/ に移行、参照先を .another-mood/docs-src/output/ に変更

### Phase 4: Hugo 連携

- [x] 4-1. Renderer として Hugo を組み込み、dev コマンドで HTML プレビュー

### Phase 5: example-project 同等機能

コンポーネント境界（Generator → Normalizer → Composer）の順に実装。Phase 1 で保存した出力を期待値として使用。

- [x] 5-1. AtomicDirWriter（safe output: tmpDir 書き出し → インプレース同期、version.json、lock）+ パススルーに組み込み
- [x] 5-2. Watcher をパイプライン基盤に載せ替え（docs-src の既存挙動を維持）
- [x] 5-3. Generator コア（definition/ 有無でパイプライン分岐、views 読み込み・マージ、Jinja2 + {% section %} インライン展開）
- [x] 5-4. Normalizer スケルトン（パススルー、検証・正規化は Phase 6）
- [x] 5-5. Composer スケルトン（パススルー、YAML DSL クエリ評価は Phase 6）
- [x] 5-6. クエリ DSL 対応（example-project/toc/entities.yaml.liquid 相当）
- [x] 5-7. Markdown prose のファイル単位正規化
- [x] 5-8. Markdown prose の出力と definition/ によるパイプライン分岐の削除

### Phase 6: メタドキュメンテーション前提機能

- [x] 6-1. エラーの伝播と汎用ドキュメンテーション
- [x] 6-2. JSON Schema によるスキーマ検証
- [x] 6-3. 辞書→配列の正規化（コンテンツデータ向け、additionalProperties パターン、再帰的）
- [x] 6-4. ユーザスキーマからのメタデータ抽出（可視化・参照整合性チェックの基盤）

### Phase 7: メタドキュメンテーション

スキーマ・クエリの「定義」をツール内蔵のテンプレートで可視化する（[meta-documentation.md](../external/app/meta-documentation.md)）。

- [x] 7-1. Composer に dataCatalog を配線し、`__definition` として views に passthrough
- [x] 7-2. Composer で normalizedQueries を `__definition.queries` として views に passthrough
- [x] 7-3. 内蔵 root（`__meta_root.md`）を導入し、エンティティ一覧を表示
- [x] 7-4. フィールド一覧と参照一覧を追加
- [x] 7-5. Query Design View を追加（Mermaid 等は使わない軽量版）

### Phase 8〜10: 追加機能

Phase 9 を **MCP サーバ対応** とし、Phase 8 をその前に実装すべき機能、Phase 10 をその後に回してよい機能として位置付ける。各タスクの実施フェーズは [phase8-tasks.md](../../phase8-tasks.md) を参照。MCP サーバの設計は [mcp-design.md](../external/app/mcp-design.md) を参照。
