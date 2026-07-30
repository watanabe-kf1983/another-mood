# 開発環境セットアップ

## 対応 Python 版

対応下限は **3.12**（`pyproject.toml` の `requires-python`）、開発は **3.13**（`.python-version`）で行う。CI はこの両端でマトリクス実行する。

下限を 3.12 に置く理由は install 手引きの成立性。Ubuntu 24.04 LTS（サポート 2029 まで）の system Python が 3.12 で、下限が 3.13 だと `pipx install` が素直に通らず、interpreter を自前調達する uv を利用者に強いることになる。それより下げないのは、PEP 695 構文（`type` 文・新ジェネリクス）を広く使っており 3.12 が構文上の床であるため。

下限を守るための仕掛けは二つ。pyright の `pythonVersion` を 3.12 に固定してあるので、3.13 専用 API はローカルの型検査でも捕まる。実行時の検証は CI マトリクスの 3.12 ジョブが担う。

## DevContainer（推奨）

VS Code + DevContainer で即座に開発可能。

1. VS Code で Remote - Containers 拡張をインストール
2. リポジトリを開き「Reopen in Container」を実行
3. コンテナ起動後、確認コマンドを実行（後述）
4. `uv run pre-commit install` を実行（pre-commit hook の有効化）

## ローカルセットアップ

DevContainer を使わない場合、以下を手動でインストールする。

1. Python 3.13 + [uv](https://docs.astral.sh/uv/)（版は上記「対応 Python 版」を参照）
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
