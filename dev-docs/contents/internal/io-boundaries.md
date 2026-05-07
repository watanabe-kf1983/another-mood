# ユーザ向け出力の境界

CLI / MCP / 将来のバックグラウンドプロセスが共有する `pipeline` と `components` の中で、ユーザ向け出力をどう扱うかの規約。

> **実装状況** — タスク [K8](../../tasks.md)（Phase 9）。実装済み。

## 規約

ユーザに見せる結果は値か callback で表す。`pipeline` と `components` は print しない。

| 種類 | 例 | 処分 |
|---|---|---|
| UX 進捗 / 成功通知 | scaffold の created/skipped、build 完了通知 | 戻り値 / `on_report` callback |
| live エラー / 異常 | stage 例外、Hugo 異常終了、watcher crash | `logger.error` / `logger.exception` |
| best-effort warning | snippet 生成失敗 | `logger.warning` |

`print(...)` を呼べるのは `cli.py` のみ (ruff `T201` で強制)。entry point の `main()` で stderr handler を install する:

```python
from logging import INFO, basicConfig
basicConfig(stream=sys.stderr, format="%(message)s", level=INFO)
```

`import logging` は使わず `from logging import ...` で名指し import する。`logging.info(...)` のような root logger 直叩きが手元から到達不能になる。

watch の per-rebuild 通知は `Pipeline` factory が受ける `on_report: Callable[[BuildReport], None]` callback で届ける。CLI が listener を install して printer 役を担う。

## command.py レイヤ

CLI / MCP の双方が呼ぶ「コマンド本体」を `src/another_mood/command.py` に集約:

```
cli.py        → command → pipeline / components/scaffold
mcp_server.py → command → pipeline / components/scaffold
```

各関数は戻り値で結果を表す。watch だけは `on_report` 必須 (per-rebuild 通知の届け先)。`ProjectConfig` の構築・検証は CLI 内で完結する (`typer.Exit` 依存)。

## 背景: なぜ stderr 直書きを構造的に避けるか

MCP stdio transport は stdout を JSON-RPC レスポンスに使う。`print("hello")` を tool 実行中に呼ぶとプロトコルが壊れる。FastMCP / mcp Python SDK は `sys.stdout` を redirect / capture / proxy しないため、依存ライブラリも含めた process 全体での stdout 汚染がプロトコル汚染になる。`stderr` は安全だが agent には届かない。

公式 servers (git / fetch / time)・独立 fastmcp・他言語 SDK のいずれも構造的防御は持たず「stderr に出せ、stdout に書くな」という規約だけで運用している。我々も同じ規約 + ruff `T201` + `command.py` の構造的分離で済ませる。`sys.stdout` プロキシや `os.dup2` fd swap は bulletproof でなく SDK 進化にも脆いため導入しない。実害の早期検知が必要なら K4 で「`mood-mcp` サブプロセス起動 + MCP test client 経由の疎通テスト」を smoke test として追加する (stdout 漏れがあれば JSON-RPC パース失敗で fail する regression detector になる)。

## 背景: logging 化の目的は agent からの抑止ではない

agent に届けるべきエラー情報は BuildReport で完結する (`error_propagation` が live tap と BuildReport の双方に書く)。logging 化の動機は「MCP で握りつぶす」ためではなく「`print` 全面禁止を機械的に強制するための統一チャネル」を用意すること。stderr の live tap は人間 CLI 利用者向けの即時フィードバックで、agent には見えなくて困らない。将来 severity-aware な配信が必要になったら handler を追加する。yagni。
