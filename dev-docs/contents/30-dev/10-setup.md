# 開発環境セットアップ

## 対応 Python 版

> **[W4 dup]** ↔ ci.yml:14-16、README.md:11、30-checks:3 (部分)。pyright 固定の段落 ↔ pyproject.toml:98-99 コメント (完全)。案: 残す (規約)。pyright の仕掛け段落は削除→pyproject コメント

対応下限は **3.12**（`pyproject.toml` の `requires-python`）、開発は **3.13**（`.python-version`）で行う。CI はこの両端でマトリクス実行する。

下限を 3.12 に置く理由は install 手引きの成立性。Ubuntu 24.04 LTS（サポート 2029 まで）の system Python が 3.12 で、下限が 3.13 だと `pipx install` が素直に通らず、interpreter を自前調達する uv を利用者に強いることになる。それより下げないのは、PEP 695 構文（`type` 文・新ジェネリクス）を広く使っており 3.12 が構文上の床であるため。

下限を守るための仕掛けは二つ。pyright の `pythonVersion` を 3.12 に固定してあるので、3.13 専用 API はローカルの型検査でも捕まる。実行時の検証は CI マトリクスの 3.12 ジョブが担う。

## DevContainer（推奨）

> **[W4 dup]** ↔ .devcontainer/README.md:14-15 (部分)。案: 残す

1. VS Code に Dev Containers 拡張をインストールする
2. リポジトリを開き「Reopen in Container」を実行する。ツール類は postCreateCommand が入れる（内訳と動作確認は [environment.md](20-environment.md)）
3. 後述の共通手順を実行する

## ローカルセットアップ

DevContainer を使わない場合、以下を手動でインストールする。

1. Python 3.13 + [uv](https://docs.astral.sh/uv/)（版は上記「対応 Python 版」を参照）
2. make
3. GitHub CLI

Claude Code と MCP サーバ群も使うなら、`.devcontainer/devcontainer.json` の features と postCreateCommand が入れているもの（Node.js、Go、Claude Code CLI、MCP Language Server、ast-grep CLI、Chrome）を同様に入れる。

## 共通手順

> **[W4 dup]** ↔ DEVELOPMENT.md:8,14 (部分)。案: 残す (dev が正本)

```bash
uv sync                      # Python 依存（ruff, pyright, pytest 等）をインストール
uv run pre-commit install    # pre-commit hook を有効化
make ci                      # 全チェック実行で環境を確認
```
