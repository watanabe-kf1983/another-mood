# Dev Container

## 環境仕様

- **ベースイメージ**: `mcr.microsoft.com/devcontainers/base:ubuntu`
- **Python**: uv で管理
- **Node.js**: npm グローバルツール用（Claude Code CLI, ast-grep）
- **Go**: MCP Language Server のビルド用

詳細は [dev-docs/contents/dev/environment.md](../dev-docs/contents/dev/environment.md) を参照。

## 使い方

1. VSCode で「Reopen in Container」を選択
2. 初回は postCreateCommand で Claude Code CLI 等が自動インストールされる
3. 動作確認は [dev-docs/contents/dev/environment.md の確認手順](../dev-docs/contents/dev/environment.md#動作確認) を参照
