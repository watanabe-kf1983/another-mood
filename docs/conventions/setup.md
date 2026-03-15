# 開発環境セットアップ

## DevContainer（推奨）

VS Code + DevContainer で即座に開発可能。

1. VS Code で Remote - Containers 拡張をインストール
2. リポジトリを開き「Reopen in Container」を実行
3. コンテナ起動後、確認コマンドを実行（後述）

DevContainer には以下が含まれる:

- Node.js 24 + TypeScript
- GitHub CLI
- Go（MCP Language Server 用）
- uv（将来の Python 移行用）
- Claude Code, ESLint, Prettier 等の VS Code 拡張

## ローカルセットアップ

DevContainer を使わない場合、上記「DevContainer」節に記載されたツール群をローカルにインストールする。

