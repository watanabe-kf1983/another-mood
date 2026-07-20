# Blob

blob は `contents_dir` に置かれた YAML・Markdown 以外の「**ツールが解釈しない不透明なファイル**」（画像・PDF・動画・CSV 等）を、内蔵コレクション **`blob`** のレコードとして扱う型。[prose](45-prose-spec.md) と対をなす — prose は `{% mood_view %}` で埋め込む「ページ素材」、blob は id で参照される「リソース」。prose と同じくパイプラインを横断する: preprocess が各ファイルを `{id, mime_type}` レコード化し、generate がバイト列を各 edition 出力へミラーし、relink / href がリンクを解決する。

## External Design

### 背景: 要求

- ソフトウェア開発ドキュメントには、mermaid.js で表現できない図表・画面レイアウト等を画像として `![]()` で埋め込む必要がある (コア要求)
- 画像に限らず、動画へのリンク、ファイル仕様書からのサンプル実物 (Excel / CSV 等) へのリンクも同様に扱う
- 出力ドキュメントの自己完結・可搬性がツールの提供価値 — 外部アップロード先へのリンクで代替しない。帰結として各 edition 出力へバイナリリソースを全コピーする
- prose の編集時 (エディタ上) から、相対パスで `![]()` / `[]()` が機能すること
- YAML レコードから id で参照でき、クエリで join できること (例: 画面エンティティ → 画面イメージ図)

なお「コンテンツではなくテンプレートの付随物となる静的アセット」(テンプレートが HTML 化したときの CSS 等) は将来の別区分であり、contents には置かず、本仕様の対象外。

### レコード形状の判断

- **id は拡張子込み** の contents 相対パス。落とすと `fig.png` / `fig.jpg` が衝突する。prose の拡張子なし id は「.md が唯一の拡張子だから成立した省略」であり、blob には適用しない
- **body を持たせない** — blob は payload (content) を持たないので、mime_type を包む階層に指すものがない。将来 text/html 等で inline content を持つ余地はレコード直下への `content` 追加で足りる (body 不要)。prose も M9 でフラット化し `{id, ..., mime_type, content}` に揃えた
- mime_type を凍結表からのみ導出する理由・絶対パスを載せない理由 (いずれも診断ビュー・中間 YAML の可搬性) は `source_loader.py` の docstring にある。バイト列自体をデータモデルに載せないのは、base64 が肥大・メモリ・diff 破壊を招くため (id が実パスを復元でき、コピー役はそこからバイトを読む)
- **blob レコードはファイル由来のみ** — YAML への blob レコードの手書きは normalize が FileValidationError で弾く (レコードはファイル自身が定義する。手書きはバイトの裏付けがないか、ファイル由来レコードとの重複にしかならない)。手書き id をパスとして解釈する経路は作らない (トラバーサル・YAML 再読み込みの穴を防ぐ)

### 出力配置: アンカーパス = 出力アドレス

各 edition ルート直下の予約名前空間 `blob/` 以下に、blob ノードのアンカーパス (`/blob/<id>`) をそのまま出力パスとしてミラーする。**アンカーパス = 出力アドレス** にすることで、リンク解決 (href が blob ノードのアンカーパスを指す) と出力配置が一致する — contents 相対パスを edition ルート直下へ直接置く旧案だと両者がずれる。`/blob/` は予約名前空間でテンプレート由来のページパスが入らないため、blob 出力パスがページパスと**構造的に衝突しえない** (衝突検査は不要)。

## Internal Design

### バイトの旅程

**Composer への受け渡し** — composer を通るのはメタデータレコードのみ。バイト列は normalize にも compose にも入らない。

**注入点は generate** — `contents_dir + id` からバイトを読み、各 edition ツリーへミラーする。generate は templates_dir / reports_file を user 入力として直接読む先例があり、後段ステージの user 入力読みはアーキテクチャの範囲内。edition ルートがどこかの知識は generator の所有物で、後段で注入すると再導出が要る。generate の一点注入なら、下流 2 レーン (md publish 行き / Hugo 行き) は既存の運搬機構が自動継承し、`mood watch` (publish なし) のライブプレビューにもバイトが届く。

**Hugo レーンは static mount 経由** — prepare_render で blob を content ツリーから分離し `static` mount として渡す。理由は、content dir 内の `.html` が Hugo 既定の `security.allowContent` にビルドごと弾かれるため。運搬機構の実装 (個別 unlink での更新・`HUGO_STATICDIR` 環境変数・削除が restart まで preview に残る Hugo 仕様) とその理由は `_sync_blobs` / `_hugo_env` の docstring に置く。

**コピー戦略** — 運搬は full copy。contents → ワークスペースは実コピー (ソースへの hardlink 禁止の理由は `_copy_blobs` の docstring)。ワークスペース内ホップの hardlink 化と増分 sync は最適化枠 ([H8](#blob-運搬の最適化-h8)、下記 Proposals)。

## Proposals

### blob 運搬の最適化 (H8) — 合意済み設計

現状の運搬は full copy — generate が contents→workspace(edition ツリー) を実コピーする境界コピーに続き、workspace 内 hop (reconcile / prepare_render / publish) も毎 run 全 blob をコピーする。実測: showcase/music の 100MB blob で build 一巡 +9s (2 edition × 8〜12 コピー)。着手時の棚卸しでは blob 1 個 (2 edition) あたり build 一巡 ~26 コピー (exclusive_read / exclusive_write sync を含む。うち Hugo 内部の static→destination コピー 2 回のみ制御外)。

設計は次の 3 本柱:

**① 境界コピーの normalize 前倒し + size+mtime 増分**

- normalize が blob バイトを出力 data ツリーの **contents 相対パスそのまま**にミラーする。レコードファイルは `<rel>.yaml` と拡張子付与されるので、`.yaml` を持ちえない blob (定義上 YAML/Markdown 以外) と構造的に衝突しない。専用名前空間は設けない
- 増分判定: stages.py が normalize へ**前回出力の実パス** (管理対象外の素の kwarg) を渡す。contents 側と size + mtime_ns が一致すれば前回出力から hardlink、不一致・前回ミラー不在・hardlink 不成立なら contents から実コピー (rsync の quick check と同じトレードオフ)
- contents → workspace は**必ず実コピー** (ユーザソースへの hardlink 禁止 — in-place 編集が workspace・公開済み出力を突き破るため。旧 `_copy_blobs` docstring の理由をここへ移設)
- バイトは既存経路に相乗り: compose の contents copytree が下流へ運び、generate は `data_dir/contents/<id>` から読む (generate の `contents_dir` 直読みは廃止)。`load_model` は拡張子で YAML のみ読むため、バイトが compose のデータモデルへ混入することはない。パイプラインへ新エッジは増やさない

**② workspace 内 hop は blob 限定でなく「全ファイル hardlink」**

共有基盤に `link_or_copy(src, dst)` を導入: dst があれば unlink → `os.link` 試行 → `OSError` (EXDEV / Windows / 非対応 FS) で `copy2` フォールバック。これを `copytree(copy_function=...)` として全コピー地点 (dir_lock の sync / exclusive_read、compose、reconcile、`_copy_blobs`、prepare_render、publish) に適用する。

blob 限定にしない理由: blob 判定の述語がツリーの根で揺れ (`<edition>/blob/…` / `data/<edition>/blob/…` / contents 相対パス)、誤判定した瞬間に inode 共有事故になる。全ファイル化なら述語が消え、安全条件が「workspace 内の全ファイルは write-once」という一枚岩の不変条件に単純化する。`link_or_copy` の「dst があれば unlink」がこの不変条件の中央実装。

**③ write-once 化 + temp の同一 FS 化**

- 棚卸しで見つかった in-place 変更は 2 箇所: prepare_render のページ `copy2` (in-place truncate) と reconcile の warnings 追記 (in-place append)。前者は `link_or_copy` 化で自動的に unlink→再作成へ、後者は read → unlink → 全文書き直しへ
- dir_lock の `mkdtemp` を `dir=out_dir.parent` (workspace root 直下) にし、temp と出力を同一 FS へ (`os.link` の成立条件。従来の /tmp は別 FS になりうる)
- 不変条件「workspace 内の全ファイルは write-once (置換は unlink→再作成)」は dir_lock の module docstring と本ファイル Internal Design に明記する

**効果見込み** — build 一巡の実コピー 26 → ~7 (境界 1 + Hugo 内部 2 + publish の別 FS フォールバック 4)。watch 定常時 (publish 先なし・blob 無変更) は Hugo 内部コピーのみ。publish の増分 sync 化 (別 FS への実コピー削減) は範囲外の後続候補。

**実施手順** — 1 ステップずつレビュー・コミットを分けて進める (各ステップ単独でもデグレなしに成立する順):

1. ③ write-once 化 — in-place 変更 2 箇所を unlink→再作成へ (hardlink 導入前の地ならし)
2. ② 全ファイル hardlink 化 — `transfer` 導入、temp 同一 FS 化、全 hop 適用
3. ①-I 境界コピーの normalize 前倒し — バイトを data ツリーに乗せ、generate の contents 直読みを廃止 (毎 run 実コピーのまま)
4. ①-II size+mtime 増分 — 前回出力からの hardlink 再利用

詳細は [tasks.yaml H8](node:/tasks/H/tasks/H8) 参照。
