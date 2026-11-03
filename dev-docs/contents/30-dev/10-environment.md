# 開発環境

開発に要るもの、その入れ方、環境が自動で行うこと。何が入っているかの一覧はここに持たない。ツールの顔ぶれと各々の用途は `.devcontainer/devcontainer.json` と `.vscode/` のコメントが、MCP サーバは `.mcp.json` が持つ。

## 対応 Python 版

対応下限は **3.12**（`pyproject.toml` の `requires-python`）、開発は **3.13**（`.python-version`）で行う。CI はこの両端でマトリクス実行する。

下限を 3.12 に置く理由は install 手引きの成立性。Ubuntu 24.04 LTS（サポート 2029 まで）の system Python が 3.12 で、下限が 3.13 だと `pipx install` が素直に通らず、interpreter を自前調達する uv を利用者に強いることになる。

それより下げないのは、PEP 695 構文（`type` 文・新ジェネリクス）を広く使っており 3.12 が構文上の床であるため。

## セットアップ

DevContainer を推奨する。VS Code に Dev Containers 拡張を入れ、リポジトリを開いて「Reopen in Container」を実行すれば、ツールの導入は postCreateCommand が行う。

DevContainer を使わない場合は `.devcontainer/devcontainer.json` を読み、features と postCreateCommand が入れているものを手で揃える（Python 版は上記）。Claude Code と MCP サーバ群を使わないなら、要るのは Python + [uv](https://docs.astral.sh/uv/)、make、GitHub CLI だけ。

どちらの場合も、最後に共通手順を実行する:

```bash
uv sync                      # Python 依存（ruff, pyright, pytest 等）をインストール
uv run pre-commit install    # pre-commit hook を有効化
make ci                      # 全チェック実行で環境を確認
```

## チェックの実行タイミング

各列の設定元:

- IDE — `.vscode/settings.json`
- Claude Code — `.claude/settings.json`（PostToolUse hook）
- Git commit — `.pre-commit-config.yaml`
- CI — `ci.yml`（`make ci` を対応 Python 版の両端でマトリクス実行。範囲と理由は上記「対応 Python 版」）

| チェック | IDE（保存時） | Claude Code（編集後） | Git commit | CI |
|---|---|---|---|---|
| フォーマット | ✓ | ✓ | ✓ | ✓（check） |
| Lint | | | | ✓ |
| 型検査 | | | | ✓ |
| テスト + カバレッジ | | | | ✓ |
| シークレット検知 | | | ✓ | ✓ |
| 段落の長さ（[ドキュメントの書き方](45-documentation.md#段落の長さ)） | | | | ✓ |
| ビルド（dev-docs / pages / showcase） | | | | ✓ |

## Playwright の作業ファイル

Playwright MCP サーバの作業ファイルは、`.gitignore` 済みの `.playwright-mcp/` 配下に集約する。ページスナップショットと console ログは MCP サーバが自動でここに出す。

スクリーンショットは `browser_take_screenshot` の `filename` に `.playwright-mcp/<name>.png` を指定する（既定では cwd 直下に落ちて散らかる）。
