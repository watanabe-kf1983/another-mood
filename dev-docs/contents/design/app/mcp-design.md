# MCP Server Design

> **一部実装** — タスク [K1〜K7](../../../tasks.md)（K1〜K5 は Phase 9、K6 は Phase 8）。K1 / K2 / K4 / K5 / K6 が実装済み、K3 は未着手、K7 は punt（後述「## 背景: watch をバックグラウンド化しない理由」）。

MCP サーバの設計。AI へのコンテキスト提供として機能する。

## 基本方針

MCP サーバは CRUD API ではなく、**AI へのコンテキスト提供**として機能する。

data/ の作成・更新・削除（CUD）は AI が直接ファイルを編集する。ツール側で CRUD API を提供しない理由:
- JSON Schema の構造に対する CRUD API（`AppendAdditionalProperty` 等）は設計が膨大になる
- AI は JSON Schema の書き方を既に知っており、YAML ファイルを直接編集できる
- ツールは YAML を読むだけでよいため、ラウンドトリップ保持（ruamel.yaml 等）が不要

## 設計原則

- **MCP と CLI の論理的機能は一致すべき**: MCP インタフェースの検討結果が CLI インタフェースの見直しの契機になりうる。差異が出たら「どちらかが間違っている」サインとして扱う
- **validate を build と分離する必要はない**: このツールは入力を変更せず副作用もない純粋関数であり、全操作が冪等かつ dry-run である。build 自体が validate を兼ねる

## 提供するツール

### build

パイプラインをワンショット同期実行し、結果を返す。CLI の `mood build` と同一のパイプライン（Hugo 描画含む）を実行する。

AI エージェントのフィードバックループ向け: edit → build → 結果取得 → 判断 → edit → build → ...

### init

新規プロジェクトのスキャフォールド。CLI の `mood init --template <name>` と同一の動作。AI が showcase の具体例を体験する経路でもある（Resources には showcase を同梱しない方針と対応）。

### start / stop

提供しない（後述「## 背景: watch をバックグラウンド化しない理由」参照）。

watch server（ファイル監視 + パイプライン自動再実行 + Hugo プレビューサーバ）は、エージェントではなく人間が visible terminal で `mood watch <dir>` を foreground 起動する運用とする。Server Instructions（K3）でその案内をエージェントに渡す。

### list_docs / read_doc

`docs/` ツリーに同梱した利用者向けドキュメント（Resources と同じ素材）を Tool 経由で公開する。`list_docs()` は目次（path / description / mimeType）を返し、`read_doc(path)` は個別ファイルの本文を返す。

Resources と内容は完全に重複するが、これは **クライアント差の吸収のための意図的な並行公開**である（後述「## 背景: クライアント差の問題」）。エージェントは Resources / Tools のどちらの経路でも同じ素材に到達できる。

## AI へのコンテキスト提供

MCP プロトコルの 4 層を使い分けてコンテキストを提供する。

### Server Instructions（初期化時に注入、200語以内）

MCP 接続時にクライアントのシステムプロンプトに注入される短い誘導文。ツール横断的なワークフロー概要と「ファイルを編集する前に Resources で仕様を確認せよ」という行動指針を伝える。

毎ターン読まれるためトークンコストが大きい。個別ツールの説明や長大なマニュアルは載せない。

### Tool description（各ツール定義に付随）

各ツールの自己完結的な説明。FastMCP では関数の docstring から自動生成される。Instructions がなくてもツール単体で使えるだけの情報を持たせる。必要に応じて参照すべき Resource の URI を明記する。

### Resources / list_docs・read_doc（オンデマンド読み込み）

Another Mood ツール自身の利用者ドキュメント（`docs/` ツリー）をオンデマンドで読めるようにする。同じ素材を 2 経路で公開する:

- **MCP Resources** (`resources/list` / `resources/read`) — 仕様上の正統な経路。Claude Code 等の capable なクライアントではエージェントが直接呼べる。人間も Browse Resources UI / `@`-mention で参照できる
- **Tools `list_docs` / `read_doc`** — 上の素材を Tool としても露出。Resources のエージェントアクセスをサポートしない MCP クライアント（Copilot Chat agent mode、Zed 等）でもエージェントが利用できるようにする

両者は同じカタログ（`docs/mcp-resources.yaml`）から登録され、URI スキーム `docs://<path>` を共有する。`list_docs()` の応答には `resource_link` content block を含めることで、capable なクライアントは Tools 経路で得た目次から native Resources 経路へリンク解決できる（仕様 `resource_link`）。

冗長な並行公開とした理由は「## 背景: クライアント差の問題」を参照。

公開対象:

- **規約の言語化**（`docs/reference/`, `docs/guides.md`）: CLI、schema、query、template の書き方を散文で説明
- **DSL の文法**（`docs/reference/schemas/`）: content-schema / schema-schema / query-schema の YAML 本体。canonical は `src/another_mood/resources/schemas/`（behavioral artifact）で、`docs/reference/schemas/` には一方向 sync の mirror を配置する（build artifact 扱い）。メタスキーマは JSON Schema の title / description で自己説明的にする（K6）

公開しないもの:

- **showcase の具体例**: `mood init --template <name>` で AI が temp ディレクトリ等に展開・体験する。MCP は「AI が *動く* ためのインタフェース」であり、静的に同梱するより init → build の体験を通して渡す方が方針と整合する
- **接続先プロジェクトの output**（`.another-mood/{project}/output/`）: build ツール経由でその場で生成・取得する

### Prompts（ユーザ起動）

MCP Prompts は人間がスラッシュコマンド等で明示的に選択する仕組みであり、AI が自律的に使うものではない。当面は使用しない。

## ドキュメント提供の一元化

利用者向けドキュメントの canonical は `docs/` の raw Markdown として一元管理し、複数チャネルで提供する:

- **GitHub**（現状） / **GitHub Pages**（将来）: 人間がブラウザで読む
- **MCP Resources / `list_docs`・`read_doc` Tools**: AI エージェントがオンデマンドで読む。同じ素材をクライアント差吸収のため両経路で公開
- **CLI --help**: 短い要約のみ。詳細はドキュメントサイト参照

`docs/` は build を介さず raw Markdown のまま配信する（どのチャネルでも同じ素材）。これにより、build 不要で GitHub から直接読める性質と、MCP に渡す素材が一致する。

AI にとっての「ドキュメント生成パイプライン全体のナビゲーター」。データの読み書きはしないが、やり方を教えてくれる存在。

## 背景: クライアント差の問題

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

## 背景: build と watch の同時実行

build（エージェントのワンショット実行）と watch（バックグラウンドのファイル監視）は同時に動作しうる。エージェントがファイルを編集すると watch が検知してパイプラインを起動し、その後エージェントが build を呼ぶケースがある。

これは問題にならない:
- **冪等性**: パイプラインは入力を変更せず副作用もない純粋関数であり、同じ入力に対して常に同じ出力を返す。二重実行しても結果は同一
- **Exclusive Write**: AtomicDirWriter による排他書き込みで、出力ディレクトリの破損は起きない

パフォーマンス上の二重実行コストが問題になった場合は、watch を一時停止する仕組み（pause_watching / resume_watching）の導入を検討する。

## 背景: watch モードが AI エージェント向けに不要な理由

AI エージェントのツール実行モデルは同期的なリクエスト→レスポンスである。常駐プロセスのログストリームから特定の変更に対する結果を抽出するのは困難であり、ワンショットの build で結果を同期取得する方がフィードバックループに適している。

ただし watch server はエージェントの背後にいる人間のために必要である。人間はブラウザでリアルタイムにドキュメントを確認したく、その仕組みは人間の直接編集・エージェント経由の編集のいずれでも機能する必要がある。

## 背景: watch をバックグラウンド化しない理由

当初は `mood watch --detach` (CLI G6) + `start_watch` / `stop_watch` (MCP K7) を提供し、エージェントから watch server をバックグラウンド起動・停止できるようにする想定だった。設計議論の結果 punt し、人間が visible terminal で `mood watch <dir>` を foreground 起動する運用に倒した。

**判断根拠**

- **価値核が小さい**: エージェントが watch を制御できることの実利は「session 開始時の 1 コマンド省略」止まり。watch は session を跨いで長時間使う性質のもので、session ごとに start/stop するわけではない
- **保守負債が割に合わない**: 推定 +200 LOC（codebase ~5% 増）、subprocess / signal / cross-platform 分岐が必要。subprocess 系は歴史的に bug の温床で、特に Windows を含む cross-platform では動作確認コストが高い（CI が `ubuntu-latest` 限定なので Windows での回帰検出は困難）
- **UX が逆に劣化する**: watch を hidden daemon にすると build / validation エラーをユーザがその場で観察する経路が断たれる。live フィードバック性は visible terminal での foreground 起動に勝てない
- **本質的に人間用機能**: 「## 背景: watch モードが AI エージェント向けに不要な理由」の通り、watch はエージェントが消費するものではない。それを「人間に代わってエージェントが起動する」薄いラッパに過ぎない start/stop は、設計上の必須度が低い

**採用する運用**

エージェントは user に「`mood watch <dir>` を別ターミナル（Windows コマンドプロンプト等）で実行してください」と案内する。Server Instructions（K3）にツール横断のガイダンスとして含める。

**将来再検討の入口**

- **正攻法路線**: mood をサービス常駐化、watch をその子、MCP は HTTP で常駐サーバと話す（Bazel daemon / Docker Desktop 流）。小ツール域を超える規模感になったら再検討
- **軽量実装路線**: 既存依存の filelock + `subprocess.creationflags` の platform 分岐で cross-platform PID file daemon は ~125 LOC で実現可能。Arch A（CLI の `mood watch` 自身が PID file lock を握る、`mood start` は `mood watch` を subprocess として spawn する）採用なら process 枚数も増えない。詳細は punt 決定時の議論履歴を参照

## 導入効果

ユーザは MCP サーバをインストールするだけで、CLAUDE.md の設定やフック設定なしに AI がツールを理解して使えるようになる。

## 提供形式

同一機能を2つのインターフェースで提供:

- **CLI**: 人間向け、シェルスクリプト連携用
- **MCP サーバ**: AI エージェント向け（ツール定義が構造化されて提供される）

CLI のみだと AI は使い方を README や --help から推測する必要がある。MCP はツールの引数・型・説明が構造化されており、AI が迷わず使える。
