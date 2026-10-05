# MCP Server Design

MCP サーバの設計。AI へのコンテキスト提供として機能する。

## External Design

### 基本方針

> **[W4 dup]** ↔ 10-architecture 設計判断#4 (c, 完全)。案: 残す (architecture は一行、理由はここ)

MCP サーバは CRUD API ではなく、**AI へのコンテキスト提供**として機能する。

contents/ の作成・更新・削除（CUD）は AI が直接ファイルを編集する。ツール側で CRUD API を提供しない理由:
- JSON Schema の構造に対する CRUD API（`AppendAdditionalProperty` 等）は設計が膨大になる
- AI は JSON Schema の書き方を既に知っており、YAML ファイルを直接編集できる
- ツールは YAML を読むだけでよいため、書き戻し（ラウンドトリップ保持）が不要

### 設計原則

> **[W4 dup]** ↔ docs/mcp.md:3-24 対応表、mcp_server.py 各 tool docstring (a/b, 部分)。案: 残す

- **MCP と CLI の論理的機能は一致すべき**: MCP インタフェースの検討結果が CLI インタフェースの見直しの契機になりうる。差異が出たら「どちらかが間違っている」サインとして扱う
- **validate を build と分離する必要はない**: このツールは入力を変更せず副作用もない純粋関数であり、全操作が冪等かつ dry-run である。build 自体が validate を兼ねる

### ドキュメント提供の一元化

> **[W4 dup]** ↔ cli.md:211、docs/catalog.yaml ヘッダ、docs_catalog/catalog.py docstring、mcp_server.py:56-57 (a/b, 部分)。構造。案: 残す (チャネル列挙は docs と同文なので縮める余地)

利用者向けドキュメントの canonical は `docs/` の raw Markdown として一元管理し、複数チャネルで提供する:

- **GitHub** のリポジトリ閲覧（将来はドキュメントサイト）: 人間がブラウザで読む
- **MCP Resources / `list_docs`・`read_doc` Tools**: AI エージェントがオンデマンドで読む。同じ素材をクライアント差吸収のため両経路で公開
- **CLI `mood docs list` / `mood docs read`**: 同じ素材を CLI からも読める。`--help` は短い要約のみで、詳細はこちらへ誘導する

`docs/` は build を介さず raw Markdown のまま配信する（どのチャネルでも同じ素材）。これにより、build 不要で GitHub から直接読める性質と、MCP に渡す素材が一致する。

AI にとっての「ドキュメント生成パイプライン全体のナビゲーター」。データの読み書きはしないが、やり方を教えてくれる存在。

### 背景: パス引数を絶対パスに限る理由

> **[W4 dup]** 第一段落の核心理由 ↔ mcp_server.py _absolute_arg docstring、command.py _require_absolute、config.py:34-37 (a, 同一)。案: 核心理由は削除→コード、issue 実例と roots/list 案は appendix

> **[W4 → appendix]**

ツールのパス引数は絶対パスのみ受け付け、相対パスは解決せずエラーで弾く。相対パスの基準になるのはサーバプロセスの作業ディレクトリで、決めるのは MCP クライアント、呼び出し元のエージェントからは見えないため。実際 Claude Code CLI はプロジェクトディレクトリで起動するが、同デスクトップ版は `$HOME` で起動し設定の `cwd` も無視する（[anthropics/claude-code#75266](https://github.com/anthropics/claude-code/issues/75266)、2026-09 に修正されないまま not planned でクローズ）。MCP 公式のデバッグ指針も、クライアント経由で起動されたサーバの作業ディレクトリは未定義でありうると明記している。

`roots/list` でクライアントにワークスペース根を訊けば、この推測自体が要らなくなる（クライアントが絶対 `file://` URI で返すプロトコル上の正解）。ただし capability は任意で、非対応クライアントは `-32601` を返す仕様であり、Claude Code デスクトップは initialize で roots を渡さない。フォールバック設計とクライアント差の検証が別途要るため今回は採らず、将来の選択肢として残す。

### 背景: クライアント差の問題

> **[W4 → appendix]**

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

> **[W4 dup]** 第一の理由 (RFC 3986 相対リンク) ↔ docs/catalog.yaml:9-12 ヘッダコメント (同じ例文) (b)。案: 第一の理由は削除→catalog.yaml、file:// 不採用は appendix

> **[W4 → appendix]**

MCP Resources の URI スキームに `docs://` カスタムスキーム + `docs/` 直下からの相対パスを採用する。例:

- `docs://guides.md`
- `docs://reference/cli.md`
- `docs://reference/schemas/content-schema.yaml`

選定理由:

- **Markdown 内の相対リンクが RFC 3986 の URI 解決規則で正しく結合される**。`docs://reference/cli.md` 上の `[view](view.md)` は `docs://reference/view.md` に解決される。docs/ の Markdown は GitHub 直閲覧用に書かれた相対リンクをそのまま AI 向けにも使える
- MCP の resource URI は仕様上「サーバ内で識別子として機能すればよく、外部リゾルバブルである必要はない」。`<scheme>://<path>` パターンは公式サンプル（`file://` / `git://` / `screen://` 等）に倣う慣習的な書式
- 別案 `file://` は不採用。実ファイルパスと誤解されうる（クライアントがホスト OS のファイルパスとしてリゾルブを試みる挙動を誘発しうる）

### 背景: watch モードが AI エージェント向けに不要な理由

> **[W4 dup]** ↔ docs/guides.md:128-133「build vs watch」(b, 結論と大筋の理由)。案?: 削除→docs (機構的理由の一文だけ appendix か)

> **[W4 → appendix]**

AI エージェントのツール実行モデルは同期的なリクエスト→レスポンスである。常駐プロセスのログストリームから特定の変更に対する結果を抽出するのは困難であり、ワンショットの build で結果を同期取得する方がフィードバックループに適している。

ただし watch server はエージェントの背後にいる人間のために必要である。人間はブラウザでリアルタイムにドキュメントを確認したく、その仕組みは人間の直接編集・エージェント経由の編集のいずれでも機能する必要がある。

### 背景: watch をバックグラウンド化しない理由

> **[W4 dup]** 運用の決定 (別ターミナルで watch を案内) ↔ mcp_server.py _INSTRUCTIONS 末尾 (a)。案: appendix のまま

> **[W4 → appendix]**

当初は `mood watch --detach` と MCP の start_watch / stop_watch ツールで、エージェントから watch server を起動・停止できるようにする想定だった。採らず、人間が visible terminal で `mood watch <dir>` を foreground 起動する運用に倒した。エージェントは利用者に「別ターミナルで `mood watch <dir>` を実行してください」と案内し、この案内は Server Instructions に含める。

- **価値核が小さい**: エージェントが watch を制御できることの実利は「session 開始時の 1 コマンド省略」止まり。watch は session を跨いで長時間使うもので、session ごとに start / stop するわけではない
- **保守負債が割に合わない**: subprocess / signal / cross-platform 分岐で 200 行規模。CI が `ubuntu-latest` 限定なので Windows での回帰検出も難しい
- **UX が劣化する**: hidden daemon にすると build / validation エラーをその場で観察する経路が断たれる
- **MCP の射程外**: MCP は同期 RPC が基本で、session を outlive する resource のライフサイクル管理は仕様の射程外。主要な MCP サーバ（Playwright / GitHub / Docker）も session 跨ぎの daemon 管理を避けている

再検討の入口は二つ。mood をサービス常駐化し MCP は HTTP で常駐サーバと話す正攻法（Bazel daemon / Docker Desktop 流。小ツール域を超えたら）と、既存依存の filelock と `subprocess.creationflags` の platform 分岐で PID file daemon を組む軽量路線（`mood watch` 自身が lock を握り `mood start` がそれを spawn する形なら 125 行程度）。

## Internal Design

### AI へのコンテキスト提供

MCP プロトコルの 4 層を使い分けてコンテキストを提供する。

#### Server Instructions（初期化時に注入、200語以内）

> **[W4 dup]** ↔ mcp_server.py:22-52 _INSTRUCTIONS (a, 方針 vs 実物)。案: 残す (方針は design)

MCP 接続時にクライアントのシステムプロンプトに注入される短い誘導文。ツール横断的なワークフロー概要と「ファイルを編集する前に `list_docs` / `read_doc` で仕様を確認せよ」という行動指針を伝える。

毎ターン読まれるためトークンコストが大きい。個別ツールの説明や長大なマニュアルは載せない。

#### Tool description（各ツール定義に付随）

各ツールの自己完結的な説明。`MCPServer` では関数の docstring から自動生成される。call site で必要な情報（目的、引数 / 戻り値の契約、CLI の同等コマンド）に絞る。Workflow やツール間の routing は Server Instructions に集約し、docstring とは重複させない。

#### Resources / list_docs・read_doc（オンデマンド読み込み）

> **[W4 dup]** ↔ mcp_server.py:56-84 (publish-as-both、resource_link) (a)、docs/mcp.md、catalog.yaml:14-19 (b) — 部分。案: 残す。「冗長な並行公開とした理由は…参照」はリンク化

Another Mood ツール自身の利用者ドキュメント（`docs/` ツリー）をオンデマンドで読めるようにする。同じ素材を 2 経路で公開する:

- **MCP Resources** (`resources/list` / `resources/read`) — 仕様上の正統な経路。Claude Code 等の capable なクライアントではエージェントが直接呼べる。人間も Browse Resources UI / `@`-mention で参照できる
- **Tools `list_docs` / `read_doc`** — 上の素材を Tool としても露出。Resources のエージェントアクセスをサポートしない MCP クライアント（Copilot Chat agent mode、Zed 等）でもエージェントが利用できるようにする

両者は同じカタログ（`docs/catalog.yaml`）から登録され、URI スキーム `docs://<path>` を共有する。`list_docs()` の応答には `resource_link` content block を含めることで、capable なクライアントは Tools 経路で得た目次から native Resources 経路へリンク解決できる（仕様 `resource_link`）。

冗長な並行公開とした理由は「背景: クライアント差の問題」を参照。

公開対象は `docs/catalog.yaml` のカタログで管理。

公開しないもの:

- **showcase の具体例**: 静的に同梱するより `mood init` 経由で AI に展開・体験させる方が「AI が *動く* ためのインタフェース」という方針と整合する
- **接続先プロジェクトの output**（`<project_dir>/.another-mood/output/`）: `build` ツール経由でその場で生成・取得する

#### Prompts（ユーザ起動）

MCP Prompts は人間がスラッシュコマンド等で明示的に選択する仕組みであり、AI が自律的に使うものではない。当面は使用しない。

### 背景: build と watch の同時実行

> **[W4 fix]** 不整合: docs/reference/cli.md:135 は同一 out-dir への concurrent build はレースしうると書く。本節の「問題にならない」は watch が既定で publish しない前提。どちらかに揃える

> **[W4 dup]** ↔ shared/component/dir_lock.py module docstring (a)、cli.md:135 (b)。注意: cli.md は同一 out-dir でレースしうると書き、前提が違う。案: 残す。前提差は不整合として別途

build（エージェントのワンショット実行）と watch（バックグラウンドのファイル監視）は同時に動作しうる。エージェントがファイルを編集すると watch が検知してパイプラインを起動し、その後エージェントが build を呼ぶケースがある。

これは問題にならない:
- **冪等性**: パイプラインは入力を変更せず副作用もない純粋関数であり、同じ入力に対して常に同じ出力を返す。二重実行しても結果は同一
- **Exclusive Write**: `exclusive_write`（`shared/component/dir_lock.py`）による排他書き込みで、出力ディレクトリの破損は起きない

パフォーマンス上の二重実行コストが問題になった場合は、watch を一時停止する仕組み（pause_watching / resume_watching）の導入を検討する。

### 背景: ライブラリは MCP Python SDK 内 MCPServer を採用

> **[W4 → appendix]**

公式 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)（PyPI: `mcp`）にバンドルされた `mcp.server.mcpserver.MCPServer` を採用。本プロジェクトは MCP サーバを stdio 上の JSON-RPC として動かすローカルプロセス用途であり、サードパーティ製の独立 [`prefecthq/fastmcp`](https://github.com/prefecthq/fastmcp) が積み増している機能（OAuth Proxy、Middleware、サーバ間 mount / proxy、Declarative JSON Config 等の Web サービス本番運用向け機能）は使い道がない。よって追加依存を増やしてまで独立 fastmcp を採用する理由がなく、公式 SDK のみを依存に取る。

両者の宣言的 API は共通である（独立 FastMCP の 1.0 が公式 SDK に寄贈されたものが SDK 1.x の `mcp.server.fastmcp.FastMCP` で、2.0 でこれが `MCPServer` に改名された。`@mcp.tool` デコレータ・型ヒントからの JSON Schema 自動生成・docstring からの description 抽出といったコア API は一貫して同等）。

なお、low-level な `mcp.server.lowlevel.Server` を直接使う選択肢もあるが、Tools / Resources を追加するたびに `list_tools` / `call_tool` ハンドラと JSON Schema 定義の boilerplate が増えるため、本プロジェクトの「関数型・宣言的を好む」スタイル（`DEVELOPMENT.md` コードスタイル節）と整合しない。`MCPServer` 層を介する。

### 背景: SDK の死荷重を受け入れる

> **[W4 → appendix]**

`mcp` は stdio-only の本ツールにも HTTP スタック（starlette / uvicorn / sse-starlette / httpx2 / cryptography 等）を引き込む。実測では、runtime 依存 26 パッケージの土台に対して SDK が **+23 パッケージ**（SDK 1.x でも +22）を足し、インストール規模がほぼ倍になる。

これを承知のうえで SDK に乗り続ける。stdio JSON-RPC を自前実装して依存ゼロ化する案（300-500 行規模）は採らない。理由は、削れるのがディスク上のパッケージ数だけなのに対し、引き受けるのがプロトコル適合の恒久的な責任だから: initialize handshake、capability negotiation、型ヒントからの JSON Schema 生成、structured output、`resource_link`、そして年次で改訂される仕様への追従。MCP の仕様追従を SDK に委ねられることが、この依存を持つ主目的であって、副作用ではない。

## Proposals

### エージェント導線の instructions 経路への移行 (J6)

MCP サーバの固有価値を問い直し、エージェントへの導線を利用者が管理するテキスト（CLAUDE.md / AGENTS.md 等の instructions ファイル）経由に寄せる。MCP サーバは派生チャネルに降格し、将来の削除候補とする。

#### 背景: MCP が運んでいるものの分解

MCP の 7 ツールはすべて `mood` サブコマンドの薄い皮であり、「MCP と CLI の論理的機能は一致すべき」の原則どおり、MCP でしかできない操作は一つもない。実際、MCP を登録できない環境（企業ポリシーで禁止）でも CLI だけで問題なく運用できている実例がある。

MCP が CLI に対して余分に運んでいるのは Server Instructions だけで、これは本ツールのエージェント向け文章のうち **唯一 `docs/` を正本としないもの** である。他のドキュメントは「`docs/` を正本とし GitHub / MCP / CLI の複数チャネルで配る」と一元化されているのに、Instructions だけは MCP というチャネルに正本ごと埋まっている。「MCP に登録せよ」と利用者に求めているのは、この埋まり方の帰結にすぎない。

「AI 向け説明文」と一括りにされがちなものは三つに分かれる:

- **内容**（ツールが何をするか、どう使うか）: 人間と AI で同一であるべきで、別版は不要。`docs/` で済んでいる
- **導線**（docs がどこにあり、いつ読むか）: 人間は README や検索で自力でたどり着くが、エージェントは文脈に書かれていなければ読みに行かない。これだけが正当に AI 固有の部分で、中身は「このディレクトリは mood で管理する。`mood --help` を見よ」程度の一行で足りる
- **プロジェクト固有の運用**（dev-docs は `dev-docs/` にあり `mood build dev-docs` で組む、等）: ツールの文書ではなくプロジェクトの文脈。書く主体はプロジェクトの持ち主で、ツールにできるのは init で種を置くことまで

結論として、ツールが出荷すべき AI 専用の文章は無い。出すべきは、良い `docs/`、エージェントが自力でたどれる導線（`mood --help` → `mood docs list` → `mood docs read`）、プロジェクトディレクトリに置く一行のポインタ、の三つ。

多くのライブラリが AI 向け文書（`llms.txt`、skill、AGENTS.md テンプレート）を別途出しているのは、人間向け docs が Web レンダリング前提で機械が取りにくい、量が多すぎて索引が要る、といった「docs が機械に読めない」症状への対処であり、方向は分離ではなく収束（人間向け docs を機械にも読める形に寄せる）である。本ツールは `docs/` が素の Markdown でパッケージに同梱され `mood docs read` で引けるので、収束後の形を最初から持っている。

#### 背景: instructions 経路が「コントローラブル」である理由

- **テキストの所有者**: MCP の Instructions はツール作者の文章がそのまま注入され、利用者にできるのはサーバの on/off だけ。instructions ファイルなら削る・直す・自分の事情を足す・PR でレビューする、すべてできる
- **届く単位**: MCP 登録はクライアントごと・利用者ごと（`.mcp.json` でプロジェクト単位にもなるが、クライアントが MCP を喋れることが前提）。リポジトリ内のファイルは、ローカルでも Web 版エージェントでも CI でも、チェックアウトすれば届く
- **信頼の境界**: システムプロンプトに第三者のテキストが注入される経路は、原理的にはプロンプトインジェクションの面であり、企業が MCP を一律禁止する理由はおそらくこれ。利用者側で統制できる経路のほうが通りやすい

ユーザスコープ / プロジェクトスコープの区別は両経路に並行して存在する（MCP の user scope ↔ `~/.claude/CLAUDE.md`、`.mcp.json` ↔ プロジェクトの CLAUDE.md）。構造は同じで、違いは中身が利用者に読めて書けるテキストかどうかだけ。

MCP 側に残る固有価値は、シェルを持たないクライアント（Claude Desktop のチャット等）への経路と、型付きスキーマの二つ。本ツールの対象利用者はコーディングエージェントなので、どちらも効きが薄い。

#### 現状の鎖

`mood --help` の冒頭は既に「schema / views / templates を書く前に `mood docs list` → `mood docs read <uri>` で仕様を読め」と指しており、`docs list` は各ページの要約つきで URI を返す。「`mood --help` を見ろ」の一言から仕様の該当ページまで二手で届く。Instructions にある作業ループ（編集 → build → `__db/` 診断出力で確認）も、`docs/guides.md` の Workflow 章に段階ごとの「どこに書き、どこで確認するか」の表として既にある。Instructions の内容で `docs/` に無いものは無い。

欠けているのは二点だけ: プロジェクトディレクトリに置く一言と、`--help` から Workflow 章への指し。

#### 案

1. **`mood --help` に作業ループへの一行を足す**。「編集 → `mood build` → `__db/` の診断ページで確認。詳細は `docs://guides.md` の Workflow」程度。既存の「仕様を読め」の一文と並べる
2. **`mood init` / `mood blueprint apply` が `<project_dir>/README.md` を生成する**。`sbdb.yaml` と同じく、ブループリントのコピーとは別の生成経路（`_generate_manifest` の隣）。全ブループリントに一様に効き、showcase 側にファイルを置かずに済む。内容は数行のポインタに限る: Another Mood（PyPI へのリンク）が管理する source-based database であること、`mood build <dir>`、コマンドは `mood --help`、仕様は `mood docs list`。構造の説明は書かない（`--help` と `guides.md` の仕事で、書くと複製になる）。読者はディレクトリを開いた同僚とエージェントの両方で、同じ文章で済む。project 直下は `contents/` の外なので content としては読まれない
3. **`docs/mcp.md` を「Using with AI agents」に改題**。冒頭を「CLAUDE.md / AGENTS.md / `.github/copilot-instructions.md` 等に次の一行を足す」に置き換え、置き場所はクライアント別の表で示す。本文は一つで、形式ごとのサンプルは作らない（複製は必ずどれかが古くなる）。MCP の設定手順は末尾の一節に降格
4. **Server Instructions を上記ポインタと同等まで縮める**。ワークフローの記述は `docs/` 側に委ね、Instructions は「`list_docs` → `read_doc` で仕様を読め、`build` で検証せよ」程度に留める
5. **将来: `mood-mcp` エントリポイントと `mcp` 依存の削除**。別 PR、`Release-Highlight: breaking`。1〜4 を先に出荷し、MCP 無しで同等の体験が得られることを確認してから落とす。削除で失うものはシェルを持たないクライアント向け経路のみで、移行案内は「CLAUDE.md に一行足す」で書ける。本ファイルの Resources / Tools 並行公開、SDK 採用理由、死荷重受容の各節は削除時に一緒に落ちる

#### 波及

- `docs/guides.md` の Quick Start にあるディレクトリ木と、`docs/reference/cli.md` の `init` / `blueprint apply` の説明に README.md を足す
- help 文中の「(also exposed via MCP)」は 5 で落ちる
- 既存プロジェクトには README.md は届かない。3 の docs ページからコピーすれば済むので、独立コマンドは急がない
- `mood init` の冪等性: 既に README.md があるときの扱い（上書きしない）を `sbdb.yaml` と揃える
- `docs/index.md` と `docs/catalog.yaml` の `mcp.md` のタイトル・要約を改題に合わせる
