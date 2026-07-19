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

### 出力配置: アンカーパス = 出力アドレス

各 edition ルート直下の予約名前空間 `blob/` 以下に、blob ノードのアンカーパス (`/blob/<id>`) をそのまま出力パスとしてミラーする。**アンカーパス = 出力アドレス** にすることで、リンク解決 (href が blob ノードのアンカーパスを指す) と出力配置が一致する — contents 相対パスを edition ルート直下へ直接置く旧案だと両者がずれる。`/blob/` は予約名前空間でテンプレート由来のページパスが入らないため、blob 出力パスがページパスと**構造的に衝突しえない** (衝突検査は不要)。

## Internal Design

### バイトの旅程

**Composer への受け渡し** — composer を通るのはメタデータレコードのみ。バイト列は normalize にも compose にも入らない。

**注入点は generate** — `contents_dir + id` からバイトを読み、各 edition ツリーへミラーする。generate は templates_dir / reports_file を user 入力として直接読む先例があり、後段ステージの user 入力読みはアーキテクチャの範囲内。edition ルートがどこかの知識は generator の所有物で、後段で注入すると再導出が要る。generate の一点注入なら、下流 2 レーン (md publish 行き / Hugo 行き) は既存の運搬機構が自動継承し、`mood watch` (publish なし) のライブプレビューにもバイトが届く。

**Hugo レーンは static mount 経由** — prepare_render で blob を content ツリーから分離し `static` mount として渡す。理由は、content dir 内の `.html` が Hugo 既定の `security.allowContent` にビルドごと弾かれるため。運搬機構の実装 (個別 unlink での更新・`HUGO_STATICDIR` 環境変数・削除が restart まで preview に残る Hugo 仕様) とその理由は `_sync_blobs` / `_hugo_env` の docstring に置く。

**コピー戦略** — 運搬は full copy。contents → ワークスペースは実コピー (ソースへの hardlink 禁止の理由は `_copy_blobs` の docstring)。ワークスペース内ホップの hardlink 化と増分 sync は最適化枠 ([H8](#blob-運搬の最適化-h8)、下記 Proposals)。

## Proposals

### blob 運搬の最適化 (H8)

現状の運搬は full copy — generate が contents→workspace(edition ツリー) を実コピーする境界コピーに続き、workspace 内 hop (reconcile / prepare_render / publish) も毎 run 全 blob をコピーする。実測: showcase/music の 100MB blob で build 一巡 +9s (2 edition × 8〜12 コピー)。

H8 では境界コピーを normalize 段へ前倒しして 1 回に絞り (size+mtime の増分 sync)、generate を含む全 workspace 内 hop を hardlink 化する。

- **安全条件** — 「workspace 内 blob は write-once」。置換は unlink→再作成で、in-place truncate は禁止 (共有 inode を壊す)
- **前提** — temp を出力と同一 FS へ (現状 /tmp は別 FS)、`os.link` + EXDEV/Windows は copy fallback

詳細は [tasks.yaml H8](node:/tasks/H/tasks/H8) 参照。
