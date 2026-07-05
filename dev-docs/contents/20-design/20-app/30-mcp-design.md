# MCP Server Design

MCP サーバの設計。AI へのコンテキスト提供として機能する。

## External Design

### 基本方針

MCP サーバは CRUD API ではなく、**AI へのコンテキスト提供**として機能する。

data/ の作成・更新・削除（CUD）は AI が直接ファイルを編集する。ツール側で CRUD API を提供しない理由:
- JSON Schema の構造に対する CRUD API（`AppendAdditionalProperty` 等）は設計が膨大になる
- AI は JSON Schema の書き方を既に知っており、YAML ファイルを直接編集できる
- ツールは YAML を読むだけでよいため、ラウンドトリップ保持（ruamel.yaml 等）が不要

### 設計原則

- **MCP と CLI の論理的機能は一致すべき**: MCP インタフェースの検討結果が CLI インタフェースの見直しの契機になりうる。差異が出たら「どちらかが間違っている」サインとして扱う
- **validate を build と分離する必要はない**: このツールは入力を変更せず副作用もない純粋関数であり、全操作が冪等かつ dry-run である。build 自体が validate を兼ねる

### ドキュメント提供の一元化

利用者向けドキュメントの canonical は `docs/` の raw Markdown として一元管理し、複数チャネルで提供する:

- **GitHub**（現状） / **GitHub Pages**（将来）: 人間がブラウザで読む
- **MCP Resources / `list_docs`・`read_doc` Tools**: AI エージェントがオンデマンドで読む。同じ素材をクライアント差吸収のため両経路で公開
- **CLI --help**: 短い要約のみ。詳細はドキュメントサイト参照

`docs/` は build を介さず raw Markdown のまま配信する（どのチャネルでも同じ素材）。これにより、build 不要で GitHub から直接読める性質と、MCP に渡す素材が一致する。

AI にとっての「ドキュメント生成パイプライン全体のナビゲーター」。データの読み書きはしないが、やり方を教えてくれる存在。

### 背景: クライアント差の問題

MCP の Resources は仕様上 "application-driven"（[2025-06-18 spec server/resources](https://modelcontextprotocol.io/specification/2025-06-18/server/resources)）であり、ホスト（クライアント）がエージェントに Resources 経路を露出するか否かは実装裁量とされている。Tools の "model-controlled"（仕様 server/tools 節）と対照的。

実際、主要クライアントの挙動は割れている (2026-05 時点):

| クライアント | エージェントが `resources/list` を呼べるか |
|---|---|
| Claude Code | ✓ `ListMcpResourcesTool` / `ReadMcpResourceTool` でラップ |
| Claude Desktop | ✗ 人間が `@` で添付する形のみ |
| VS Code Copilot Chat (agent mode) | ✗ 公式に「Resources は agent loop に露出しない」とアナウンス |
| Cursor | △ 手動 attach 中心 |
| Cline / Continue | ✓ |
| Zed | ✗ Tools / Prompts のみ |

このため、Resources のみで公開すると **エージェントが docs を引けるのは Claude Code 系統に限定**される。本ツールは「特定の MCP クライアントに依存しない」立ち位置なので、これは設計目標との不整合。

サーバ側で取れる対策はコミュニティで概ね収束しており、**同じ素材を Resources と Tools の両方で公開する** "publish-as-both" パターンが支配的（AWS Documentation MCP、Microsoft Learn MCP、Context7、GitHub MCP server 他）。Tool 名のデファクトは存在しないが、`list_<domain>` + `read_<domain>(path)` のペア構造は filesystem / AWS Docs / Notion など複数で採用されており、最も踏み固められた牛道。本ツールはこれに倣い `list_docs` + `read_doc(path)` を採用する。

Resources を残す理由:
- Claude Code の `@`-mention で個別 doc をコンテキストに添付する人間 UX が機能する
- VSCode MCP extension の Browse Resources UI で開発者が公開対象を可視化できる
- 将来 Copilot Chat / Cursor 等が Resources をエージェントに露出する場合に Tools 並行公開を撤去できる柔軟性

将来クライアント差が解消したら Tools 経路を撤去する判断は容易（`list_docs` / `read_doc` の利用者はエージェントのみのため）。

### 背景: `docs://` URI スキーム

MCP Resources の URI スキームに `docs://` カスタムスキーム + `docs/` 直下からの相対パスを採用する。例:

- `docs://guides.md`
- `docs://reference/cli.md`
- `docs://reference/schemas/content-schema.yaml`

選定理由:

- **Markdown 内の相対リンクが RFC 3986 の URI 解決規則で正しく結合される**。`docs://reference/cli.md` 上の `[query](query.md)` は `docs://reference/query.md` に解決される。docs/ の Markdown は GitHub 直閲覧用に書かれた相対リンクをそのまま AI 向けにも使える
- MCP の resource URI は仕様上「サーバ内で識別子として機能すればよく、外部リゾルバブルである必要はない」。`<scheme>://<path>` パターンは公式サンプル（`file://` / `git://` / `screen://` 等）に倣う慣習的な書式
- 別案 `file://` は不採用。実ファイルパスと誤解されうる（クライアントがホスト OS のファイルパスとしてリゾルブを試みる挙動を誘発しうる）

### 背景: watch モードが AI エージェント向けに不要な理由

AI エージェントのツール実行モデルは同期的なリクエスト→レスポンスである。常駐プロセスのログストリームから特定の変更に対する結果を抽出するのは困難であり、ワンショットの build で結果を同期取得する方がフィードバックループに適している。

ただし watch server はエージェントの背後にいる人間のために必要である。人間はブラウザでリアルタイムにドキュメントを確認したく、その仕組みは人間の直接編集・エージェント経由の編集のいずれでも機能する必要がある。

### 背景: watch をバックグラウンド化しない理由

当初は `mood watch --detach` + MCP の start_watch / stop_watch ツールを提供し、エージェントから watch server をバックグラウンド起動・停止できるようにする想定だった。設計議論の結果 punt し、人間が visible terminal で `mood watch <dir>` を foreground 起動する運用に倒した。

**判断根拠**

- **価値核が小さい**: エージェントが watch を制御できることの実利は「session 開始時の 1 コマンド省略」止まり。watch は session を跨いで長時間使う性質のもので、session ごとに start/stop するわけではない
- **保守負債が割に合わない**: 推定 +200 LOC（codebase ~5% 増）、subprocess / signal / cross-platform 分岐が必要。subprocess 系は歴史的に bug の温床で、特に Windows を含む cross-platform では動作確認コストが高い（CI が `ubuntu-latest` 限定なので Windows での回帰検出は困難）
- **UX が逆に劣化する**: watch を hidden daemon にすると build / validation エラーをユーザがその場で観察する経路が断たれる。live フィードバック性は visible terminal での foreground 起動に勝てない
- **本質的に人間用機能**: 「背景: watch モードが AI エージェント向けに不要な理由」の通り、watch はエージェントが消費するものではない。それを「人間に代わってエージェントが起動する」薄いラッパに過ぎない start/stop は、設計上の必須度が低い

**MCP プロトコルの射程との関係**

MCP プロトコル自体が「同期 RPC + 進捗通知 + キャンセル」を基本とし、session を outlive する resource のライフサイクル管理は仕様の射程外（async 概念がない、background task supervision の primitive もない）。実際、主要な MCP サーバは session 跨ぎの background daemon 管理を **避ける** 設計を採っている:

- **Playwright MCP**: browser を MCP server の子プロセスとして connection 中だけ alive。session 終了で browser も終了
- **GitHub MCP**: API wrapper に徹する（resource lifecycle は GitHub 側で持続）
- **Docker MCP**: container の lifecycle は OS の Docker daemon に委譲し、MCP は client 役

「session 跨ぎで persist する watch を MCP 経由で制御する」は、本ツール固有の難所というより **MCP エコシステム全体が踏み込んでいない領域**。punt したのは、避けるべき難所として認識した上での選択であり、エコシステムの傾向とも整合的。「正攻法」が HTTP + 自前 daemon を要求するのは、MCP の射程を超えるからこそ別プロトコルが要る、という関係。

> **メンタルモデル**: MCP は「**エージェントの知覚と作用域を拡張する**」プロトコル。同期 RPC で扱える範囲のみを射程とし、background プロセスの supervision や session 跨ぎ state は射程外。

**採用する運用**

エージェントは user に「`mood watch <dir>` を別ターミナル（Windows コマンドプロンプト等）で実行してください」と案内する。Server Instructions にツール横断のガイダンスとして含める。

**将来再検討の入口**

- **正攻法路線**: mood をサービス常駐化、watch をその子、MCP は HTTP で常駐サーバと話す（Bazel daemon / Docker Desktop 流）。小ツール域を超える規模感になったら再検討
- **軽量実装路線**: 既存依存の filelock + `subprocess.creationflags` の platform 分岐で cross-platform PID file daemon は ~125 LOC で実現可能。Arch A（CLI の `mood watch` 自身が PID file lock を握る、`mood start` は `mood watch` を subprocess として spawn する）採用なら process 枚数も増えない。詳細は punt 決定時の議論履歴を参照

## Internal Design

### AI へのコンテキスト提供

MCP プロトコルの 4 層を使い分けてコンテキストを提供する。

#### Server Instructions（初期化時に注入、200語以内）

MCP 接続時にクライアントのシステムプロンプトに注入される短い誘導文。ツール横断的なワークフロー概要と「ファイルを編集する前に Resources で仕様を確認せよ」という行動指針を伝える。

毎ターン読まれるためトークンコストが大きい。個別ツールの説明や長大なマニュアルは載せない。

#### Tool description（各ツール定義に付随）

各ツールの自己完結的な説明。FastMCP では関数の docstring から自動生成される。call site で必要な情報（目的、引数 / 戻り値の契約、CLI の同等コマンド）に絞る。Workflow やツール間の routing は Server Instructions に集約し、docstring とは重複させない。

#### Resources / list_docs・read_doc（オンデマンド読み込み）

Another Mood ツール自身の利用者ドキュメント（`docs/` ツリー）をオンデマンドで読めるようにする。同じ素材を 2 経路で公開する:

- **MCP Resources** (`resources/list` / `resources/read`) — 仕様上の正統な経路。Claude Code 等の capable なクライアントではエージェントが直接呼べる。人間も Browse Resources UI / `@`-mention で参照できる
- **Tools `list_docs` / `read_doc`** — 上の素材を Tool としても露出。Resources のエージェントアクセスをサポートしない MCP クライアント（Copilot Chat agent mode、Zed 等）でもエージェントが利用できるようにする

両者は同じカタログ（`docs/catalog.yaml`）から登録され、URI スキーム `docs://<path>` を共有する。`list_docs()` の応答には `resource_link` content block を含めることで、capable なクライアントは Tools 経路で得た目次から native Resources 経路へリンク解決できる（仕様 `resource_link`）。

冗長な並行公開とした理由は「背景: クライアント差の問題」を参照。

公開対象は `docs/catalog.yaml` のカタログで管理。

公開しないもの:

- **showcase の具体例**: 静的に同梱するより `mood init` 経由で AI に展開・体験させる方が「AI が *動く* ためのインタフェース」という方針と整合する
- **接続先プロジェクトの output**（`.another-mood/{project}/output/`）: `build` ツール経由でその場で生成・取得する

#### Prompts（ユーザ起動）

MCP Prompts は人間がスラッシュコマンド等で明示的に選択する仕組みであり、AI が自律的に使うものではない。当面は使用しない。

### 背景: build と watch の同時実行

build（エージェントのワンショット実行）と watch（バックグラウンドのファイル監視）は同時に動作しうる。エージェントがファイルを編集すると watch が検知してパイプラインを起動し、その後エージェントが build を呼ぶケースがある。

これは問題にならない:
- **冪等性**: パイプラインは入力を変更せず副作用もない純粋関数であり、同じ入力に対して常に同じ出力を返す。二重実行しても結果は同一
- **Exclusive Write**: AtomicDirWriter による排他書き込みで、出力ディレクトリの破損は起きない

パフォーマンス上の二重実行コストが問題になった場合は、watch を一時停止する仕組み（pause_watching / resume_watching）の導入を検討する。

### 背景: ライブラリは MCP Python SDK 内 FastMCP を採用

公式 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)（PyPI: `mcp`）にバンドルされた `mcp.server.fastmcp.FastMCP` を採用。本プロジェクトは MCP サーバを stdio 上の JSON-RPC として動かすローカルプロセス用途であり、サードパーティ製の独立 [`prefecthq/fastmcp`](https://github.com/prefecthq/fastmcp) が積み増している機能（OAuth Proxy、Middleware、サーバ間 mount / proxy、Declarative JSON Config 等の Web サービス本番運用向け機能）は使い道がない。よって追加依存を増やしてまで独立 fastmcp を採用する理由がなく、公式 SDK のみを依存に取る。

両者の宣言的 API は共通である（独立 FastMCP の 1.0 が公式 SDK に寄贈されたものが `mcp.server.fastmcp.FastMCP` であり、両者で `@mcp.tool` デコレータ・型ヒントからの JSON Schema 自動生成・docstring からの description 抽出といったコア API は同等）。万一乗り換えが必要になった場合も、import 文の付け替えで済む規模の差。

なお、low-level な `mcp.server.Server` を直接使う選択肢もあるが、Tools / Resources を追加するたびに `list_tools` / `call_tool` ハンドラと JSON Schema 定義の boilerplate が増えるため、本プロジェクトの「関数型・宣言的を好む」スタイル（`DEVELOPMENT.md` コードスタイル節）と整合しない。FastMCP 層を介する。
