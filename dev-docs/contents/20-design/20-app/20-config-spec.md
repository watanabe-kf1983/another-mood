# 設定システム仕様

## External Design

### 設定の管轄範囲

設定システムが扱うのは**起動パラメータ**（どう実行し、どこへ出すか: `project_dir` / `out_dir` / `site_dir` / `tmp_dir` / `host` / `port`）のみ。

ソースレイアウト（`definition/schema.yaml` 等のパス群）は設定ではなく sbdb フォーマット世代が定めるプロジェクト構造であり、`resolve_layout`（`layout.py`）が導出する。レイアウトの `RB_*` 個別オーバーライドは廃止済み（[G10](node:/tasks/G/tasks/G10) — フォーマット世代を名乗りながらファイル位置を動かせるのは宣言と矛盾するため）。

### 設定の読み込み優先順位

設定は以下の順序でマージされる（後のものが優先）:

1. デフォルト値
2. 設定ファイル（未実装 — [G2](node:/tasks/G/tasks/G2)）
3. 環境変数
4. CLI 引数

## 背景: preflight の順序

ソースパスの存在検証は `ProjectConfig.verify` ではなくレイアウト解決の後段で行い、失敗は `UserError` 系の precondition 例外として CLI / MCP 境界で出す（build-report には積まない）。`project_dir` の検証（CWD 配下 + 存在）だけが config 側に残る — manifest を読む前提条件のため。

あるべき preflight 順序: `project_dir` 検証 → manifest 読込（V1）→ 版ゲート（V4）→ レイアウト解決 → ソース存在検証。レイアウト解決を manifest 読込より後に置くのは、`resolve_layout` が将来 `sbdb_version` で版ディスパッチする拡張点であり、非対応版プロジェクトには「Source paths not found」より先に「非対応版」を出すべきため（詳細は [60-sbdb-manifest](node:/prose/20-design/20-app/60-sbdb-manifest)）。

## Proposals

### namespace_root — CWD を CLI 層に閉じ込める

#### 問題

`config.py` が `Path.cwd()` を直接読んでおり（`verify` の包含チェックと `_another_mood_root` の相対パス導出）、command 層が呼び出し元の立ち位置に依存する不純な関数になっている。CWD はプロセスの環境状態であって入力ではないので、依存方向（`{cli, mcp_server}` → `command` → ...）に反する。

これが MCP 経由で二つの症状として出ている:

- **`out_dir` が CWD 相対で返る**。エージェントはサーバの CWD を知らない（決めたのは MCP クライアント）ため解決できない。[MCP 設計](30-mcp-design.md)の Server Instructions が「編集途中に `output/__entity_defs/` を読んで解決結果を確かめよ」と指示しているのに、返したパスでは辿れない
- **サーバ CWD 配下にないプロジェクトをビルドできない**。`mcp_server` が `verify()` を呼ぶため、エージェントには見えず選べもしないディレクトリを基準に拒否される

#### 設計

`.another-mood/<tail>` がぶら下がる根 — かつ `<tail>` を決める名前空間の基準 — を `namespace_root` として明示的な入力にする。

| 層 | 既定値 | 結果 |
|---|---|---|
| CLI | `Path.cwd()` | `<cwd>/.another-mood/<project_dir からの相対パス>/`（現行と同じ配置） |
| MCP | `project_dir` | `tail` が `.` に潰れ `<project_dir>/.another-mood/` |

双方から optional に明示指定できる（CLI は `--namespace-root`、MCP はツール引数）。

同じ導出ロジックが両者を賄い、包含チェックは `namespace_root` に対して行う。MCP 既定では自明に真になるので、MCP がチェックを迂回する必要はない。`Path.cwd()` を呼ぶのは CLI 層だけになる。

境界層（CLI / MCP）がパスを絶対化してから渡す。これにより「command 層に入るパスは既に絶対」という不変条件が立つ。

この不変条件が要るのは、`Path.cwd()` の明示的な呼び出しを潰すだけでは足りないため。`.resolve()` は相対パスに対して暗黙に CWD を基準にするので、CWD 依存は `components` / `pipeline` まで潜り込んでいる — `blueprints` / `stages` の `project_dir.resolve().name`、`diagnostic` の表示用 `file.resolve()`、`hugo` アダプタの subprocess 用絶対化。入ってくるパスが既に絶対なら、これらの `.resolve()` は絶対化の意味を失い symlink 正規化だけが残る。

#### 命名の検討

`namespace_root` に落ち着くまでに挙がった候補と却下理由:

- `base_dir` — 「基準」の語が多義で、何の基準かが名前から立ち上がらない
- `working_dir` — `tmp_dir` のコメントが既に「Working dir」を名乗っている（同じ設定クラス内での衝突）
- `workspace_dir` — pipeline の `Workspace` と衝突する。加えてワークスペースは MCP サーバを起動するエディタ側が所有する概念で、mood が知り得るのはクライアントが与えた CWD だけ。持っていない概念の所有権を主張する名前になる
- `invocation_dir` — MCP が `project_dir` を束縛する以上「呼び出しの根」ではなくなる

#### 採らなかった選択肢

- **MCP の出力を temp dir に置く**: エージェントのファイルアクセスは概ねワークスペースに閉じており、temp dir はサンドボックス外になりうる。エージェントが確実に読める場所は、自身が指定した `project_dir` だけ
- **MCP の基準を `project_dir.parent` にする**: 深さ 1 のプロジェクトだけ CLI と出力先が一致する（`dev-docs/` → `<repo>/.another-mood/dev-docs/`）が、`showcase/starter` では一致しない。さらに `project_dir` がワークスペース根そのものだと親がサンドボックス外へ出る。`project_dir` を基準にすればこの破綻がない
- **CLI も入力ディレクトリ内出力へ統一する**: 名前空間付け・包含チェック・CWD 依存がまとめて消える魅力はあるが、[プロジェクト構成](10-project-structure.md)の「`.another-mood/` を CWD 直下に配置する理由」に正面から反する。CWD 配下のディレクトリを `project_dir` にするのが CLI の主要ユースケースであり、この挙動は変えない。破壊的変更に見合わない
- **生成ディレクトリに自己無視 `.gitignore` を書き込む**（`.pytest_cache` 方式）: 入れ子の `.another-mood/` が `/.another-mood/` の 1 行に捕まらない問題は消せるが、gitignore は利用者に委ねる

#### 帰結

- `out_dir` が絶対パスになる。CLI は `out_dir` を表示しない（`tap` が内部で読むだけ）ため、利用者から見える変化はない
- MCP 既定では**入力ディレクトリの中に出力が置かれる**。[プロジェクト構成](10-project-structure.md)の「入力ディレクトリはユーザのコンテンツ領域」に対する意図的な例外 — エージェントが確実に読める場所が `project_dir` しかないため（temp dir はエージェントのサンドボックス外になりうる）。gitignore は利用者に委ねる
- `10-project-structure.md` の「CWD 直下に配置する理由」「`<projectDir>` ごとに分離する理由」は、CWD 固有の規則から `namespace_root` の規則へ一般化される。CLI の既定が CWD である以上、書かれている理由自体は失効しない

### 設定ファイル (G2)

- ファイル名: `another-mood.config.json`
- 配置場所: プロジェクトルート
- 対応フォーマット: JSON
- スコープ注意: ソースレイアウトは設定項目にしない（G10 で設定システムの管轄外と決定 — 「設定の管轄範囲」参照）
