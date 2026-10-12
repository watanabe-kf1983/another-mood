# CLI Design

`mood` CLI の設計。人間と AI エージェントが同じ入口から使う。

## External Design

### 基本方針

CLI は CRUD API ではない。contents/ の作成・更新・削除（CUD）は利用者や AI エージェントがファイルを直接編集する（[ソースは標準形式のテキスト、ツールは読むだけ](../../10-concept/10-product.md#ソースは標準形式のテキストツールは読むだけ)）。

### 設計原則

- **validate を build と分離する必要はない**: このツールは入力を変更せず副作用もない純粋関数であり、全操作が冪等かつ dry-run である。build 自体が validate を兼ねる
- **AI エージェント専用の経路も文章も持たない**: MCP サーバは提供しない。エージェントはシェルから人間と同じ `mood` を叩き、同じ `docs/` を読む。ツールの使い方は人間とエージェントで同一であるべきで、別版は要らない。sbdb プロジェクトに来たエージェントへの導線は、プロジェクト直下に生成する `README.md` が担う（[背景](../../90-appendix/20-design/25-entrypoints/20-cli-design.md#mcp-サーバを提供しない理由)）

### ドキュメント提供の一元化

利用者向けドキュメントの canonical は `docs/` の raw Markdown として一元管理し、複数チャネルで提供する:

- **GitHub** のリポジトリ閲覧（将来はドキュメントサイト）: 人間がブラウザで読む
- **CLI `mood docs list` / `mood docs read`**: パッケージに同梱した同じ素材をオンデマンドで読む。エージェントはプロジェクトを離れずに仕様を引ける。`--help` は短い要約のみで、詳細はこちらへ誘導する

`docs/` は build を介さず raw Markdown のまま配信する（どのチャネルでも同じ素材）。これにより、build 不要で GitHub から直接読める性質と、CLI で引ける素材が一致する。公開対象は `docs/catalog.yaml` のカタログで管理する。

### 背景: `docs://` URI スキーム

`mood docs` が doc を指す URI に、`docs://` カスタムスキーム + `docs/` 直下からの相対パスを採用する。例:

- `docs://guides.md`
- `docs://reference/cli.md`
- `docs://reference/schemas/content-schema.yaml`

選定理由:

- **Markdown 内の相対リンクが RFC 3986 の URI 解決規則で正しく結合される**。`docs://reference/cli.md` 上の `[view](view.md)` は `docs://reference/view.md` に解決される。docs/ の Markdown は GitHub 直閲覧用に書かれた相対リンクをそのまま `mood docs read` の引数に使える
- 別案 `file://` は不採用。実ファイルパスと誤解されうる（読み手がホスト OS のファイルパスとしてリゾルブを試みる挙動を誘発しうる）

### 背景: エージェントは watch でなく build を使う

AI エージェントのツール実行モデルは同期的なリクエスト→レスポンスである。常駐プロセスのログストリームから特定の変更に対する結果を抽出するのは困難であり、ワンショットの build で結果を同期取得する方がフィードバックループに適している。

ただし watch server はエージェントの背後にいる人間のために必要である。人間はブラウザでリアルタイムにドキュメントを確認したく、その仕組みは人間の直接編集・エージェント経由の編集のいずれでも機能する必要がある。

### 背景: watch をバックグラウンド化しない理由

当初は `mood watch --detach` で、エージェントから watch server を起動・停止できるようにする想定だった。採らず、人間が visible terminal で `mood watch <dir>` を foreground 起動する運用に倒した。エージェントは利用者に「別ターミナルで `mood watch <dir>` を実行してください」と案内する。

- **価値核が小さい**: エージェントが watch を制御できることの実利は「session 開始時の 1 コマンド省略」止まり。watch は session を跨いで長時間使うもので、session ごとに start / stop するわけではない
- **保守負債が割に合わない**: subprocess / signal / cross-platform 分岐で 200 行規模。CI が `ubuntu-latest` 限定なので Windows での回帰検出も難しい
- **UX が劣化する**: hidden daemon にすると build / validation エラーをその場で観察する経路が断たれる

再検討の入口は二つ。mood をサービス常駐化する正攻法（Bazel daemon / Docker Desktop 流。小ツール域を超えたら）と、既存依存の filelock と `subprocess.creationflags` の platform 分岐で PID file daemon を組む軽量路線（`mood watch` 自身が lock を握り `mood start` がそれを spawn する形なら 125 行程度）。

## Internal Design

### 背景: build と watch の同時実行

build（エージェントのワンショット実行）と watch（バックグラウンドのファイル監視）は同時に動作しうる。エージェントがファイルを編集すると watch が検知してパイプラインを起動し、その後エージェントが build を呼ぶケースがある。

これは問題にならない:
- **冪等性**: パイプラインは入力を変更せず副作用もない純粋関数であり、同じ入力に対して常に同じ出力を返す。二重実行しても結果は同一
- **Exclusive Write**: `exclusive_write`（`shared/component/dir_lock.py`）による排他書き込みで、出力ディレクトリの破損は起きない

パフォーマンス上の二重実行コストが問題になった場合は、watch を一時停止する仕組み（pause_watching / resume_watching）の導入を検討する。
