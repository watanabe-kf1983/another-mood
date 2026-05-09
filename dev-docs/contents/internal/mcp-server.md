# MCP Server

MCP サーバの内部設計。利用者視点の振る舞い仕様（What）は [design/app/mcp-design.md](../design/app/mcp-design.md) を参照。本ドキュメントは How を扱う。

## 位置づけ

MCP サーバは CLI と並ぶ独立したエントリポイント。CLI / MCP の双方が共通の `command` 層を経由して `pipeline` / `components/scaffold` を呼び出す。依存ルールは:

```
cli         → command → pipeline / components/scaffold / components/docs_catalog → components/shared
mcp_server  → command → pipeline / components/scaffold / components/docs_catalog → components/shared
```

CLI と MCP のエントリは別バイナリとして公開する（後述「## 背景: CLI と MCP のエントリは分離する」）。共通コマンド層 (`src/another_mood/command.py`) の I/O 規約は [io-boundaries.md](io-boundaries.md) を参照。

## モジュール配置

- `src/another_mood/cli.py` — 人間向け CLI（Typer）
- `src/another_mood/mcp_server.py` — MCP サーバ（FastMCP）

ファイル名を `mcp.py` ではなく `mcp_server.py` としたのは、MCP 公式 Python SDK のパッケージ名 `mcp` との import 名衝突を避けるため。

`pyproject.toml [project.scripts]` で `mood` と `mood-mcp` を別バイナリとして公開する（後述「## 背景: CLI と MCP のエントリは分離する」）。

## Resources 公開

公開対象は [design/app/mcp-design.md](../design/app/mcp-design.md) で確定したとおり `docs/` ツリー一式（人間向け GitHub プレビューと AI 向け MCP Resources の素材を一元化）。

### URI スキーム: `docs://<path>`

`docs://` カスタムスキーム + `docs/` 直下からの相対パスを採用する。例:

- `docs://guides.md`
- `docs://reference/cli.md`
- `docs://reference/schemas/content-schema.yaml`

選定理由:

- **Markdown 内の相対リンクが RFC 3986 の URI 解決規則で正しく結合される**。`docs://reference/cli.md` 上の `[query](query.md)` は `docs://reference/query.md` に解決される。docs/ の Markdown は GitHub 直閲覧用に書かれた相対リンクをそのまま AI 向けにも使える
- MCP の resource URI は仕様上「サーバ内で識別子として機能すればよく、外部リゾルバブルである必要はない」。`<scheme>://<path>` パターンは公式サンプル（`file://` / `git://` / `screen://` 等）に倣う慣習的な書式
- 別案 `file://` は不採用。実ファイルパスと誤解されうる（クライアントがホスト OS のファイルパスとしてリゾルブを試みる挙動を誘発しうる）

### カタログ駆動の静的登録: `docs/mcp-resources.yaml`

公開対象は `docs/mcp-resources.yaml`（ホワイトリスト）に列挙する。`mcp_server.py` 起動時に 1 回読んで `add_resource` で登録する。スキャン方式は採らない。

```yaml
resources:
  - path: guides.md
    description: ...
  - path: reference/cli.md
    description: ...
  ...
```

選定理由:

- **`description` は AI に提示される一次メタデータ**であり、最も適した文面は `docs/index.md` / `docs/reference/index.md` で人間向けに既に書かれているリンク説明文。これを各ファイルから自動抽出（H1 / 先頭段落等）するより、catalog に直接書く方が明示的かつ意図とズレない
- スキャンだと `index.md` のような agent 向けに公開不要なナビゲーションファイルを毎回除外ロジックで弾く必要が出る。catalog 方式ならホワイトリストで自然に制御できる
- catalog の場所を `docs/` 直下にしたのは、MCP に公開する素材（docs/ 配下）と、その目次を同じツリーに置くため。`docs/index.md` のリンク説明と並べてメンテできる

`docs/mcp-resources.yaml` の `description` は `docs/index.md` / `docs/reference/index.md` のリンク説明文と手書きで同期する。3 箇所同期になるが、いずれも頻繁に動かないため当面はコスト許容。drift が顕在化したら catalog を真としてリンク説明側を生成する自動化を再検討する。

### mimeType の導出

拡張子から導出する（`.md` → `text/markdown`、`.yaml` → `application/yaml`）。catalog 上に書かない理由は重複情報になり drift 源になるため。

### 名前 (`name`) の導出

`docs/` からの相対パス（例 `reference/cli.md`）を採用する。FastMCP / MCP プロトコル上 `name` は人間可読な識別子であり、ファイル名のみ（`cli.md`）にすると `cli.md` が複数出ない場合でも将来衝突しうるため、相対パスで一意化する。

### docs/ の wheel 同梱

`docs/` はリポジトリルート直下に置かれているため、wheel に含めるよう [pyproject.toml](../../../pyproject.toml) の `[tool.hatch.build.targets.wheel.force-include]` で `docs → another_mood/_docs` をマップする。`mcp_server.py` の `_docs_root()` は `importlib.resources` 経由で `_docs` を検索し、editable install ではリポジトリ直下の `docs/` にフォールバックする（`components/scaffold/blueprints.py:_showcase_root` と同パターン）。

### Tools 並行公開: `list_docs` / `read_doc`

[design/app/mcp-design.md](../design/app/mcp-design.md) の「## 背景: クライアント差の問題」節で論じたとおり、Resources のエージェントアクセスをサポートしないクライアント（Copilot Chat agent mode、Zed 等）でもエージェントが docs を引けるよう、同じ素材を Tool としても並行公開する。

```python
@mcp.tool()
def list_docs() -> list[ResourceLink]: ...

@mcp.tool()
def read_doc(uri: str) -> str: ...
```

実装方針:

- **データの単一ソース化**: Resources 登録と Tool 実装は同じ catalog を共有する。drift しない
- **`list_docs` の戻り値は `ResourceLink` 配列**: 仕様 ([Tools spec 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)) の `resource_link` content block を返すことで、capable なクライアント (Claude Code) は Tool 経由で得た目次から native Resources 経路にリンクをたどれる。Tools 経路と Resources 経路を仕様サポート範囲で繋ぐ
- **`read_doc(uri)` の引数は `docs://` URI**: `list_docs` の応答に出る `uri` をそのまま渡せるため、エージェントから見て round-trip がストレート。catalog 上に存在しない URI は `ValueError` で拒否（catalog 外のファイル読み出し防止）
- **Tool 名の選定**: `list_docs` / `read_doc` は filesystem / AWS Documentation MCP / Notion 等で踏み固められた `list_<domain>` + `read_<domain>(path)` 系統の牛道に乗る。MCP プロトコルメソッド名 (`list_resources` / `read_resource`) を Tool 名に流用するサーバは皆無（"そのままタダ乗りできるデファクト" は存在せず、命名は自前で決める必要があった）

## テスト方針

mcp_server 層に対する pytest 単体テストは書かない。理由:

- mcp_server.py は FastMCP の API に既存機能（pipeline / config / ファイル読み出し）を bind するアダプタ層であり、自前のロジックを持たない（cli.py が Typer に bind するアダプタ層であるのと同じ構造で、本プロジェクトでは Typer 経路に対しても CLI テストを書いていない）
- pytest で書ける内容は「FastMCP のラッピングが機能しているか」になり、これは FastMCP 自身のテストで担保される範囲
- ロジックの守備範囲は委譲先（`pipeline` / `components/*`）の単体テストに任せる

mcp_server 層の保証は **MCP クライアントからの E2E 動作確認** で行う:

1. **VSCode Copilot Chat**（Agent モード）からの呼び出し — リポジトリ直下の `.vscode/mcp.json` に `another-mood` を登録して使う
2. **Claude Code** からの呼び出し — リポジトリ直下の `.mcp.json` に登録して使う（`mcp__another-mood__*` ツールとして見える）
3. （任意）**MCP Inspector** — `npx @modelcontextprotocol/inspector mood-mcp` で MCP プロトコルを直接叩く軽量 UI。デバッグ時に有用

各タスクの完了時、PR 説明に動作確認の証跡（呼び出し画面のスクリーンショットまたは応答ログ）を残す。E2E が通らない実装は完了とみなさない。型チェック（pyright）と既存テストが通るだけでは、書いたコードが実際に MCP サーバとして稼働するかは何一つ確認されないため。

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
