# 開発チェック

チェックの実行タイミング。各列の設定元は、IDE が `.vscode/settings.json`、Claude Code が `.claude/settings.json`（PostToolUse hook）、Git commit が `.pre-commit-config.yaml`、CI が `ci.yml`（`make ci` を対応 Python 版の両端でマトリクス実行。範囲と理由は [setup.md](10-setup.md)）。

| チェック | IDE（保存時） | Claude Code（編集後） | Git commit | CI |
|---|---|---|---|---|
| フォーマット | ✓ | ✓ | ✓ | ✓（check） |
| Lint | | | | ✓ |
| 型検査 | | | | ✓ |
| テスト + カバレッジ | | | | ✓ |
| シークレット検知 | | | ✓ | ✓ |
| ビルド（dev-docs / pages / showcase） | | | | ✓ |
