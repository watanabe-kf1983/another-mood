# Blob

blob は `contents_dir` に置かれた YAML・Markdown 以外の「**ツールが解釈しない不透明なファイル**」（画像・PDF・動画・CSV 等）を、内蔵コレクション **`blob`** のレコードとして扱う型。[prose](20-prose-spec.md) と対をなす — prose は `{% render %}` で埋め込む「ページ素材」、blob は id で参照される「リソース」。prose と同じくパイプラインを横断する: preprocess が各ファイルを `{id, mime_type}` レコード化し、generate がバイト列を各 edition 出力へミラーし、relink / href がリンクを解決する。

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

**Composer のデータモデルにはメタデータのみ** — composer の JSON データモデルを通るのはメタデータレコードだけ (`load_model` は拡張子で YAML のみ読むため、バイトはモデルへ混入しない)。バイト列自体は normalize が出力 data ツリーに載せ、compose の contents copytree が下流へ相乗りで運ぶ — パイプラインに blob 専用のエッジは足さない。

**境界コピーは normalize** — normalize が `contents/<id>` のバイトを出力 data ツリーの **contents 相対パスそのまま** (`data/contents/<id>`) にミラーする。レコードファイルは `<rel>.yaml` と拡張子付与されるので、`.yaml` を持ちえない blob (定義上 YAML/Markdown 以外) と構造的に衝突しない — 専用名前空間は不要。generate は下流の `data_dir/contents/<id>` から読んで各 edition ツリーへ `/blob/<id>` としてミラーする (generate の contents 直読み・`contents_dir` パラメータは廃止)。edition ルートがどこかの知識は generator の所有物なので、edition 別ミラーは generate に残す。下流 2 レーン (md publish 行き / Hugo 行き) は既存の運搬機構が自動継承し、`mood watch` (publish なし) のライブプレビューにもバイトが届く。

**Hugo レーンは static mount 経由** — prepare_render で blob を content ツリーから分離し `static` mount として渡す。理由は、content dir 内の `.html` が Hugo 既定の `security.allowContent` にビルドごと弾かれるため。運搬機構の実装 (個別 unlink での更新・`HUGO_STATICDIR` 環境変数・削除が restart まで preview に残る Hugo 仕様) とその理由は `_sync_blobs` / `_hugo_env` の docstring に置く。

**コピー戦略は hardlink + 増分再利用** — workspace 内の hardlink 運搬と「全ファイル write-once」不変条件は [Component Communication](index.md) の総論（運搬機構）に従う。blob 固有なのは境界コピーと増分再利用の 2 点:

- **境界だけが実コピー、ソースへの hardlink は禁止** — contents → workspace の 1 回だけが実コピー。ユーザソースへ hardlink すると in-place 編集が workspace・公開済み出力を突き破るため禁止 (理由は `_mirror_blob_bytes` のコメント)。
- **前回出力からの増分再利用** — stages.py が normalize へ前回出力の実パスを管理対象外の kwarg (`prev_out_dir`) で渡す。contents と size + mtime_ns が一致すれば前回出力から hardlink 再利用、不一致・前回不在・hardlink 不成立なら contents から実コピー (rsync の quick check と同じトレードオフ — mtime のみの変更も再コピー扱い)。リンク先行・比較後で、比較対象の inode を固定してから判定する (前回出力の並行置換とのレース回避)。詳細は `_reuse_unchanged`。

**背景: 効果 (実測)** — showcase/music (100MB blob・2 edition) を同一 FS 上で計測すると、build 一巡で materialize される blob の実バイトコピー (distinct inode) は **12 → 3**。3 の内訳は境界コピー 1 + Hugo の static→destination 内部コピー 2 (制御外)。md レーンは境界の 1 inode を publish 出力まで hardlink 共有する。warm 無変更リビルドは境界コピーも再利用し実コピー 0。publish 先が別 FS の場合のみ publish 境界で実コピーが復活する (publish の増分化は範囲外の後続候補)。
