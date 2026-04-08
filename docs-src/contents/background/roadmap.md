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

- [ ] 7-1. Composer に dataCatalog を配線し、`__metadata` として views に passthrough
- [ ] 7-2. Composer で normalizedQueries を `__metadata.queries` として views に passthrough
- [ ] 7-3. 内蔵 root（`__meta_root.md`）を導入し、エンティティ一覧を表示
- [ ] 7-4. フィールド一覧と参照一覧を追加
- [ ] 7-5. Query Design View を追加（Mermaid 等は使わない軽量版）

### Phase 8〜10: 追加機能

Phase 9 を **MCP サーバ対応** とし、Phase 8 をその前に実装すべき機能、Phase 10 をその後に回してよい機能として位置付ける。

Phase 8 開始時に、以下を含めて全タスクをいったん整理する:

- このロードマップに未タスク化のまま `docs-src/contents/` に仕様だけ書かれている項目を拾い出し、タスク化する
- Phase 7 から繰り越した項目（ER 図、Table View / Query View 等）を再評価する
- 各タスクを Phase 8 / Phase 9 / Phase 10 に振り分ける

#### 現時点での候補（振り分け前）

- [ ] YAML DSL クエリ評価の拡充（from / join / where / group_by / select / sort）
- [ ] Markdown パーサー（データソースとしての Markdown 読み込み）
- [ ] 参照整合性チェック（references.yaml、`--strict`）
- [ ] 標準テンプレート（ER図、DFD、CRUD マトリクス） — ER 図は join / 参照整合性が動いてから視認性が出るため Phase 7 から繰り越し
- [ ] メタ可視化: Table View / Query View（実データ表示） — 動的名前引きの Generator 拡張が必要になるため Phase 7 から繰り越し
- [ ] MCP サーバ対応（AI へのコンテキスト提供: validate 結果、DSL 仕様、schema 要約、生成結果確認） — Phase 9
- [ ] 計算機能プラグインのインターフェース検討（例: ファンクションポイント算出プラグイン）
- [ ] `docs-src/` 自身のリファクタリング — 現状はツールの機能を十分に活かせておらず、本来このツールで書かれるべき構造になっていない。dog-fooding を通じたツール機能の十分性検証を兼ねる（Phase 8 で実施するか Phase 10 に回すかは整理時に判断。十分性なきまま MCP サーバ作りに進む是非も併せて検討）
