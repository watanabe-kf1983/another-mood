# MCP Server Design

> **未実装** — タスク [K1〜K6](../../../tasks.md)（K1〜K5 は Phase 9、K6 は Phase 8）

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

watch server（ファイル監視 + パイプライン自動再実行 + Hugo プレビューサーバ）をバックグラウンドで起動・停止する。CLI の `mood watch` と同一の機能。人間がブラウザでドキュメントを閲覧するためのもの。エージェントが人間の指示に応じて制御する。

## AI へのコンテキスト提供

MCP プロトコルの 4 層を使い分けてコンテキストを提供する。

### Server Instructions（初期化時に注入、200語以内）

MCP 接続時にクライアントのシステムプロンプトに注入される短い誘導文。ツール横断的なワークフロー概要と「ファイルを編集する前に Resources で仕様を確認せよ」という行動指針を伝える。

毎ターン読まれるためトークンコストが大きい。個別ツールの説明や長大なマニュアルは載せない。

### Tool description（各ツール定義に付随）

各ツールの自己完結的な説明。FastMCP では関数の docstring から自動生成される。Instructions がなくてもツール単体で使えるだけの情報を持たせる。必要に応じて参照すべき Resource の URI を明記する。

### Resources（オンデマンド読み込み）

Another Mood ツール自身の利用者ドキュメント（`docs/` ツリー）を MCP Resources として公開する。AI は `resources/list` で目次を取得し、`resources/read` で個別ドキュメントを読む。

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
- **MCP Resources**: AI エージェントがオンデマンドで読む
- **CLI --help**: 短い要約のみ。詳細はドキュメントサイト参照

`docs/` は build を介さず raw Markdown のまま配信する（どのチャネルでも同じ素材）。これにより、build 不要で GitHub から直接読める性質と、MCP に渡す素材が一致する。

AI にとっての「ドキュメント生成パイプライン全体のナビゲーター」。データの読み書きはしないが、やり方を教えてくれる存在。

## 背景: build と watch の同時実行

build（エージェントのワンショット実行）と watch（バックグラウンドのファイル監視）は同時に動作しうる。エージェントがファイルを編集すると watch が検知してパイプラインを起動し、その後エージェントが build を呼ぶケースがある。

これは問題にならない:
- **冪等性**: パイプラインは入力を変更せず副作用もない純粋関数であり、同じ入力に対して常に同じ出力を返す。二重実行しても結果は同一
- **Exclusive Write**: AtomicDirWriter による排他書き込みで、出力ディレクトリの破損は起きない

パフォーマンス上の二重実行コストが問題になった場合は、watch を一時停止する仕組み（pause_watching / resume_watching）の導入を検討する。

## 背景: watch モードが AI エージェント向けに不要な理由

AI エージェントのツール実行モデルは同期的なリクエスト→レスポンスである。常駐プロセスのログストリームから特定の変更に対する結果を抽出するのは困難であり、ワンショットの build で結果を同期取得する方がフィードバックループに適している。

ただし watch server はエージェントの背後にいる人間のために必要である。人間はブラウザでリアルタイムにドキュメントを確認したく、その仕組みは人間の直接編集・エージェント経由の編集のいずれでも機能する必要がある。そのためエージェントが watch server の起動・停止を制御できるようにする。

## 導入効果

ユーザは MCP サーバをインストールするだけで、CLAUDE.md の設定やフック設定なしに AI がツールを理解して使えるようになる。

## 提供形式

同一機能を2つのインターフェースで提供:

- **CLI**: 人間向け、シェルスクリプト連携用
- **MCP サーバ**: AI エージェント向け（ツール定義が構造化されて提供される）

CLI のみだと AI は使い方を README や --help から推測する必要がある。MCP はツールの引数・型・説明が構造化されており、AI が迷わず使える。
