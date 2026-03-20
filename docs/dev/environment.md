# 開発環境定義

開発環境に含めるツール・設定の一覧と、その理由。

## DevContainer

### ベースイメージ

Python + uv が使えるイメージを選定する。

### Features

| Feature | 用途 |
|---|---|
| GitHub CLI | PR 作成等の Git 操作 |
| Go | MCP Language Server のビルド |

### Claude Code 永続化

`~/.claude` を名前付きボリュームにマウントし、コンテナ再作成時に Claude Code の設定・会話履歴を保持する。ボリュームの所有権は postCreateCommand で非 root ユーザに変更する。

### postCreateCommand

コンテナ作成後に以下をインストールする:

- Claude Code CLI
- 言語の LSP サーバ（MCP Language Server 経由で Claude Code が使用）
- ast-grep CLI（MCP サーバが使用）

## VSCode

### 拡張

| 拡張 | 用途 |
|---|---|
| Claude Code | AI アシスタント |
| Ruff | Python フォーマッタ・リンタ |
| YAML | スキーマ・データファイルの編集支援 |
| Markdown Mermaid | Mermaid 図のプレビュー |
| GitHub Actions | CI ワークフローの編集支援 |

拡張の一覧は `.vscode/extensions.json`（推奨拡張）と `.devcontainer/devcontainer.json`（自動インストール）の両方に記載する。

### 設定

- `editor.formatOnSave: true` — 保存時にフォーマッタを自動実行
- デフォルトフォーマッタをプロジェクトのフォーマッタ（Ruff）に設定

## MCP サーバ

`.mcp.json` に Claude Code 用の MCP サーバを定義する。

| サーバ | 用途 |
|---|---|
| language-server | LSP 経由のコード解析（定義ジャンプ、参照検索等） |
| ast-grep | 構文パターンによるコード検索 |
| context7 | ライブラリドキュメントの取得 |

language-server は言語に応じた LSP サーバを指定する（Python なら pyright 等）。テストランナーの MCP サーバは、採用するテストフレームワークに応じて選定する。

## .gitignore

言語非依存で維持するパターン:

- `reports/` — テスト・カバレッジレポート
- `.claude/settings.local.json` — Claude Code ローカル設定（個人の API キー等）
- `.DS_Store` — macOS メタデータ

言語依存のパターン（依存ディレクトリ、ビルド出力等）は環境構築時に追加する。
