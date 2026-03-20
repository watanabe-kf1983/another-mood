# 開発環境セットアップ

## DevContainer（推奨）

VS Code + DevContainer で即座に開発可能。

1. VS Code で Remote - Containers 拡張をインストール
2. リポジトリを開き「Reopen in Container」を実行
3. コンテナ起動後、確認コマンドを実行（後述）

DevContainer には以下が含まれる:

- Python (uv)
- GitHub CLI
- Go（MCP Language Server 用）
- Claude Code, Ruff 等の VS Code 拡張

## ローカルセットアップ

DevContainer を使わない場合、上記「DevContainer」節に記載されたツール群をローカルにインストールする。

## 自動チェック

各チェックがどこで走るかは [checks.md](checks.md) を参照。
