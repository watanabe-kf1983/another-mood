# MCP Server

MCP サーバの内部設計。利用者視点の振る舞い仕様（What）は [design/app/mcp-design.md](../design/app/mcp-design.md) を参照。本ドキュメントは How を扱う。

> **未実装** — タスク [K1〜K7](../../tasks.md)（Phase 9）。本ドキュメントは K1（FastMCP 骨格）の方針記述から始め、K2 以降の実装に応じて追記する。

## 位置づけ

MCP サーバは CLI と並ぶ独立したエントリポイント。CLI / MCP の双方が `pipeline` を組み立てて呼び出す並列の関係であり、両者を連結しない。依存ルールは:

```
cli         → pipeline → components/* → components/shared
mcp_server  → pipeline → components/* → components/shared
```

CLI と MCP のエントリは別バイナリとして公開する（後述「## 背景: CLI と MCP のエントリは分離する」）。共通ロジック（`ProjectConfig` 構築等）の抽出層（command 層）を間に挟むかは K1 / K2 段階では判断保留。実 Tools が登場する K4 / K5 着手時に再検討する。

## モジュール配置

- `src/another_mood/cli.py` — 人間向け CLI エントリ。Typer app（build / watch / init）。MCP 関連は含めない
- `src/another_mood/mcp_server.py` — MCP サーバエントリ。`mcp.server.fastmcp.FastMCP` インスタンスの構築と stdio での起動。Tools / Resources / Instructions の配線もここから始める
- `pyproject.toml [project.scripts]`:
  - `mood = "another_mood.cli:main"` — 人間向け CLI
  - `mood-mcp = "another_mood.mcp_server:main"` — MCP サーバ起動専用

ファイル名を `mcp.py` ではなく `mcp_server.py` としたのは、MCP 公式 Python SDK のパッケージ名 `mcp` との import 名衝突を避けるため。

K2 以降でファイルが肥大化したら `mcp_server/` パッケージに昇格させる（Tools / Resources / Instructions の各モジュール分割）。当面は単一ファイルで開始する。

## K1 のスコープ

骨格のみを通す。具体的には:

- `mcp.server.fastmcp.FastMCP` インスタンスの生成と `mcp.run()` 経由の stdio 起動
- `pyproject.toml` への `mood-mcp` エントリ追加
- 動作確認用のダミー Tool（`ping() -> "pong"` 程度）を 1 つ登録
- 本リポジトリ自身の MCP クライアント設定（`.vscode/mcp.json`、`.mcp.json`）に `another-mood` を登録

含めないもの: 実 Tools（build / init 等）、Resources、Server Instructions（K2 以降）。

ダミー Tool は K4 / K5 で実 Tool が入るタイミングで削除する（K1〜K3 期間中の動作確認手段として保持）。

出口: VSCode Copilot Chat および Claude Code から `mood-mcp` 経由で `ping` を呼び出し、`pong` が返ってくることを目視確認する。

## テスト方針

mcp_server 層に対する pytest 単体テストは書かない。理由:

- mcp_server.py は FastMCP の API に既存機能（pipeline / config / ファイル読み出し）を bind するアダプタ層であり、自前のロジックを持たない（cli.py が Typer に bind するアダプタ層であるのと同じ構造で、本プロジェクトでは Typer 経路に対しても CLI テストを書いていない）
- pytest で書ける内容は「FastMCP のラッピングが機能しているか」になり、これは FastMCP 自身のテストで担保される範囲
- ロジックの守備範囲は委譲先（`pipeline` / `components/*`）の単体テストに任せる

mcp_server 層の保証は **MCP クライアントからの E2E 動作確認** で行う:

1. **VSCode Copilot Chat**（Agent モード）からの呼び出し — リポジトリ直下の `.vscode/mcp.json` に `another-mood` を登録して使う
2. **Claude Code** からの呼び出し — リポジトリ直下の `.mcp.json` に登録して使う（`mcp__another-mood__*` ツールとして見える）
3. （任意）**MCP Inspector** — `npx @modelcontextprotocol/inspector mood-mcp` で MCP プロトコルを直接叩く軽量 UI。デバッグ時に有用

K1 では (1) と (2) を完了基準とし、PR 説明に動作確認の証跡（呼び出し画面のスクリーンショットまたは応答ログ）を残す。E2E が通らない実装は完了とみなさない。型チェック（pyright）と既存テストが通るだけでは、書いたコードが実際に MCP サーバとして稼働するかは何一つ確認されないため。

## 背景: ライブラリは MCP Python SDK 内 FastMCP を採用

公式 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)（PyPI: `mcp`）にバンドルされた `mcp.server.fastmcp.FastMCP` を採用。本プロジェクトは MCP サーバを stdio 上の JSON-RPC として動かすローカルプロセス用途であり、サードパーティ製の独立 [`prefecthq/fastmcp`](https://github.com/prefecthq/fastmcp) が積み増している機能（OAuth Proxy、Middleware、サーバ間 mount / proxy、Declarative JSON Config 等の Web サービス本番運用向け機能）は使い道がない。よって追加依存を増やしてまで独立 fastmcp を採用する理由がなく、公式 SDK のみを依存に取る。

両者の宣言的 API は共通である（独立 FastMCP の 1.0 が公式 SDK に寄贈されたものが `mcp.server.fastmcp.FastMCP` であり、両者で `@mcp.tool` デコレータ・型ヒントからの JSON Schema 自動生成・docstring からの description 抽出といったコア API は同等）。万一乗り換えが必要になった場合も、import 文の付け替えで済む規模の差。

なお、low-level な `mcp.server.Server` を直接使う選択肢もあるが、Tools / Resources を追加するたびに `list_tools` / `call_tool` ハンドラと JSON Schema 定義の boilerplate が増えるため、本プロジェクトの「関数型・宣言的を好む」スタイル（[DEVELOPMENT.md](../../../DEVELOPMENT.md) コードスタイル節）と整合しない。FastMCP 層を介する。

## 背景: CLI と MCP のエントリは分離する

人間向けの `mood` と MCP サーバ起動専用の `mood-mcp` を別バイナリとして公開する。`mood` のサブコマンドとして `mood mcp` を提供する案も検討したが採用しない。

理由:

- 通信プロトコルが違う。CLI は人間が叩いて結果を読むもの、MCP サーバは stdio で JSON-RPC を待ち受けて MCP クライアント（Claude Desktop / Code 等）と対話するもの。**人間が `mood mcp` を直接叩いても何もできない**
- そのため `mood --help` の一覧に `mcp` を並べると、人間に「叩けるコマンド」として誤って案内することになる。CLI の `--help` は人間向けコマンドの純度を保つ
- MCP クライアントへの登録時の `command` フィールドは `mood-mcp` の方が意図が明確（`{"command": "mood", "args": ["mcp"]}` より `{"command": "mood-mcp"}`）

ユーザのインストール体験は変わらない（`pip install another-mood` で両バイナリが同時に入る）。`pyproject.toml [project.scripts]` のエントリを 2 つにするだけ。

## 背景: ワークスペース名衝突は許容して動作確認する

VSCode Copilot Chat の E2E 動作確認は、本リポジトリ直下の `.vscode/mcp.json` を使って行う。サブワークスペース (例: `tests/manual/test-workspace/`) を切り出して名前衝突を回避する案も検討したが採用しない。

理由: DevContainer の仕様上、リポジトリは `/workspaces/{repo-name}/` 固定マウントであり、サブワークスペースを開いてもパスの親階層に `another-mood` が残る。Agent (Copilot Chat) が「現在のワークスペース」を判定するときに、開いているフォルダ名だけでなくパス親階層・DevContainer 名・Git リポジトリ root 等の複数のシグナルを参照するため、サブワークスペース化では完全な切り離しができない（K1 動作確認時の Copilot Chat ログで観察）。

完全な切り離しを目指すと postCreateCommand で `/tmp/test-workspace/` を生成する等の DevContainer 改造が要るが、工数に対する効果が薄い。本リポジトリの開発時動作確認では「ワークスペース名衝突 → ツール選択の誤誘導」が発生しうることを認識した上で、衝突を許容する。

利用者向けの実利用シナリオ（プロジェクト名と無関係な任意のワークスペースから MCP サーバを呼ぶ形）の検証は、利用者向けドキュメントタスク（[L7](../../tasks.md): docs/ への MCP セクション追加 + 配布手順）でユーザグローバル登録手順として案内する。
