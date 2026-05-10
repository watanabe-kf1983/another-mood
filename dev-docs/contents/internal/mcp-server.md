# MCP Server

MCP サーバの内部設計。利用者視点の振る舞い仕様（What）は [design/app/mcp-design.md](../design/app/mcp-design.md) を参照。本ドキュメントは How を扱う。

## 背景: ライブラリは MCP Python SDK 内 FastMCP を採用

公式 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)（PyPI: `mcp`）にバンドルされた `mcp.server.fastmcp.FastMCP` を採用。本プロジェクトは MCP サーバを stdio 上の JSON-RPC として動かすローカルプロセス用途であり、サードパーティ製の独立 [`prefecthq/fastmcp`](https://github.com/prefecthq/fastmcp) が積み増している機能（OAuth Proxy、Middleware、サーバ間 mount / proxy、Declarative JSON Config 等の Web サービス本番運用向け機能）は使い道がない。よって追加依存を増やしてまで独立 fastmcp を採用する理由がなく、公式 SDK のみを依存に取る。

両者の宣言的 API は共通である（独立 FastMCP の 1.0 が公式 SDK に寄贈されたものが `mcp.server.fastmcp.FastMCP` であり、両者で `@mcp.tool` デコレータ・型ヒントからの JSON Schema 自動生成・docstring からの description 抽出といったコア API は同等）。万一乗り換えが必要になった場合も、import 文の付け替えで済む規模の差。

なお、low-level な `mcp.server.Server` を直接使う選択肢もあるが、Tools / Resources を追加するたびに `list_tools` / `call_tool` ハンドラと JSON Schema 定義の boilerplate が増えるため、本プロジェクトの「関数型・宣言的を好む」スタイル（[DEVELOPMENT.md](../../../DEVELOPMENT.md) コードスタイル節）と整合しない。FastMCP 層を介する。
