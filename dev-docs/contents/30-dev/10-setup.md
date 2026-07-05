# 開発環境セットアップ

## DevContainer（推奨）

VS Code + DevContainer で即座に開発可能。

1. VS Code で Remote - Containers 拡張をインストール
2. リポジトリを開き「Reopen in Container」を実行
3. コンテナ起動後、確認コマンドを実行（後述）
4. `uv run pre-commit install` を実行（pre-commit hook の有効化）

## ローカルセットアップ

DevContainer を使わない場合、以下を手動でインストールする。

1. Python 3.13 + [uv](https://docs.astral.sh/uv/)
2. Go（MCP Language Server のビルド用）
3. GitHub CLI
4. make（macOS は標準搭載、Linux もほぼ標準）
5. Node.js（Claude Code が使用。Python 開発自体には不要）

インストール後:

```bash
uv sync                      # Python 依存（ruff, pyright, pytest 等）をインストール
uv run pre-commit install    # pre-commit hook を有効化
make ci                      # 全チェック実行で環境を確認
```

各ツールの用途の詳細は [environment.md](20-environment.md) を参照。
