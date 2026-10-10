# 開発環境定義

開発環境に含めるツール・設定の一覧と、その理由。

## DevContainer

> **[W4 dup]** ベースイメージ・Features・postCreateCommand ↔ .devcontainer/README.md:5-8,15 (部分)、10-setup:25 (c)。案?: .devcontainer/README.md と二重。どちらかに寄せる

### ベースイメージ

`mcr.microsoft.com/devcontainers/base:ubuntu`。Python 本体は入れず、uv feature が `.python-version` の interpreter を調達する。

### Features

| Feature | 用途 |
|---|---|
| Node.js | Claude Code CLI、ast-grep CLI のインストール（npm 経由） |
| Go | MCP Language Server のビルド |
| GitHub CLI | PR 作成等の Git 操作 |
| uv | Python パッケージマネージャ |

### 動作確認

コンテナ起動後に以下を実行し、環境が正常であることを確認する。

```bash
# ユーザー・ボリューム
whoami                  # → vscode
ls -la ~/.claude        # マウント済み、所有者が vscode

# Features
node --version
go version
gh --version
uv --version

# postCreateCommand でインストールされるツール
claude --version
mcp-language-server --help
ast-grep --version
```

VSCode 拡張パネルで拡張テーブルの全拡張がインストールされていること。

### Claude Code 永続化

`~/.claude` を名前付きボリュームにマウントし、コンテナ再作成時に Claude Code の設定・会話履歴を保持する。ボリュームの所有権は postCreateCommand で非 root ユーザに変更する。

### postCreateCommand

コンテナ作成後に以下をインストールする:

- Claude Code CLI
- MCP Language Server（Claude Code が LSP を叩くためのブリッジ。LSP 本体の pyright-langserver は `uv sync` で入る）
- ast-grep CLI（MCP サーバが使用）
- Google Chrome（Playwright MCP サーバが使用、`npx playwright install chrome`）
- Noto CJK フォント（Playwright で CJK 文字を含む描画の検証に必要、`apt-get install fonts-noto-cjk`）

## VSCode

### 拡張

> **[W4 dup]** 表 ↔ .vscode/extensions.json / devcontainer.json の設定本体 (コメント無し、用途列のみ付加)。「コードから読めるものは書かない」との関係。案?: 残す (JSON にはコメントが書けない) か、用途を落として一覧だけ設定に委ねる

| 拡張 | 用途 |
|---|---|
| Claude Code | AI アシスタント |
| Python | IntelliSense, venv 検出 |
| Pylance | 型チェック・コード補完（pyright ベース） |
| Python Debugger | デバッグ |
| Python Environment Manager | 仮想環境の管理 |
| Ruff | Python フォーマッタ・リンタ |
| Makefile Tools | Makefile の編集支援 |
| EditorConfig | `.editorconfig` の適用（非 Python ファイルのインデント・改行・文末改行の統一） |
| YAML | スキーマ・データファイルの編集支援 |
| Markdown Mermaid | Mermaid 図のプレビュー |
| GitHub Actions | CI ワークフローの編集支援 |

拡張の一覧は `.vscode/extensions.json`（推奨拡張）と `.devcontainer/devcontainer.json`（自動インストール）の両方に記載する。

### 設定

- `editor.formatOnSave: true` — 保存時にフォーマッタを自動実行
- Python のデフォルトフォーマッタを Ruff に設定

## MCP サーバ

> **[W4 dup]** 表 ↔ .mcp.json の設定本体 (コメント無し)。案?: 同上

`.mcp.json` に Claude Code 用の MCP サーバを定義する。

| サーバ | 用途 |
|---|---|
| language-server | LSP 経由のコード解析（定義ジャンプ、参照検索等） |
| ast-grep | 構文パターンによるコード検索 |
| context7 | ライブラリドキュメントの取得 |
| playwright | ヘッドレスブラウザ駆動。Mermaid 等の生成図を実機レンダリングして見た目を検証する用途。`--headless` 固定 |
| another-mood | このリポジトリ自身の MCP サーバ（`uv run mood-mcp`）。dev-docs / showcase を編集する際の dog-fooding |

language-server は pyright-langserver を `--stdio` で起動する。

`.vscode/mcp.json` は VS Code 内蔵の MCP クライアント向けで、another-mood だけを定義する。

## .gitignore

> **[W4 dup]** ↔ .gitignore の各見出しコメント (完全)。案: 削除→.gitignore

Python の生成物（`__pycache__/`、`.venv/`、各ツールのキャッシュ）のほかに無視するもの:

- `reports/` — テスト・カバレッジレポート
- `/.another-mood/` — `mood build` の出力
- `/_site/` — `make pages` が組む GitHub Pages サイト
- `/.playwright-mcp/` — Playwright MCP の作業ファイル
- `.claude/settings.local.json` — Claude Code の個人設定
- `.DS_Store` — macOS メタデータ
