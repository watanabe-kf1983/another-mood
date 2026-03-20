# Roadmap

### Phase 1: 移行準備

- [x] 1-1. TypeScript 実装から未ドキュメントの仕様を救出・ドキュメント化
- [x] 1-2. example-project/output/docs を gitignore 外して commit（現行出力を期待値として保存）
- [x] 1-3. TypeScript コード・設定を削除

### Phase 2: Python 環境構築 + プロジェクト設定

- [ ] 2-1. Python 環境構築（DevContainer, VSCode 拡張, MCP 設定）
  - DevContainer: ベースイメージを base:ubuntu に変更、features（uv, Node, Go, GitHub CLI）
  - postCreateCommand: Claude Code CLI, ast-grep, mcp-language-server
  - .vscode/extensions.json: Python, Ruff, EditorConfig, YAML, Mermaid, GitHub Actions, Claude Code
  - ドキュメント更新（.devcontainer/README.md, docs/dev/environment.md）
- [ ] 2-2. プロジェクト設定（uv init, CI, ツール導入・配線）
  - .mcp.json: language-server を pyright に変更
  - uv init → pyproject.toml 作成
  - .gitignore に Python パターン追加（.venv, __pycache__ 等）
  - GitHub Actions CI の骨格（uv sync + 空のステップ）
  - ツールを1つずつ追加し、IDE on save / pre-commit hook / CI に配線:
    - ruff format → IDE on save, pre-commit hook, CI
    - ruff check → CI
    - pyright → CI
    - pytest + pytest-cov → CI（カバレッジ 85%）
    - secretlint → pre-commit hook, CI
  - Claude Code PostToolUse hook（ruff format）
  - main ブランチ保護

### Phase 3: パススルーパイプライン（自己ドッグフーディング開始）

- [ ] 3-1. build コマンド（contents/ → .reqs-builder/output/ にコピー）
- [ ] 3-2. dev コマンド（build + ファイル監視で自動再実行）
- [ ] 3-3. docs/ を docs/contents/ に移行、CLAUDE.md 等の参照先を .reqs-builder/output/ に変更

### Phase 4: Hugo 連携

- [ ] 4-1. Renderer として Hugo を組み込み、dev コマンドで HTML プレビュー

### Phase 5: example-project 同等機能

コンポーネント境界（Normalizer / Composer / Generator）に沿って実装。Phase 1 で保存した出力を期待値として使用。具体的なタスク分割は着手時に決定。

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
