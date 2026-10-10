# Blob

blob は `contents_dir` に置かれた YAML・JSON・Markdown 以外の「**ツールが解釈しない不透明なファイル**」（画像・PDF・動画・CSV 等）を、内蔵コレクション **`blob`** のレコードとして扱う型。[prose](25-prose-spec.md) と対をなす — prose は `render` フィルタで埋め込む「ページ素材」、blob は id で参照される「リソース」。レコードの形は `docs/reference/schema.md` の blob 節が約束する。この型を置いた要求は[背景](../../90-appendix/20-design/50-normalizer/27-blob-spec.md#要求)、バイト列を出力まで運ぶ経路は [運搬機構](../40-communication/index.md#運搬機構)。

## External Design

### レコード形状の判断

- **id は拡張子込み** の contents 相対パス。落とすと `fig.png` / `fig.jpg` が衝突する。prose の拡張子なし id は「.md が唯一の拡張子だから成立した省略」であり、blob には適用しない
- **body を持たせない** — blob は payload (content) を持たないので、mime_type を包む階層に指すものがない。将来 text/html 等で inline content を持つ余地はレコード直下への `content` 追加で足りる (body 不要)。prose も同じくフラットな `{id, ..., mime_type, content}` に揃えてある
- **バイト列はデータモデルに載せない** — base64 が肥大・メモリ・diff 破壊を招くため。id が実パスを復元でき、コピー役はそこからバイトを読む
- **blob レコードはファイル由来のみ** — YAML への blob レコードの手書きは normalize が FileValidationError で弾く。手書き id をパスとして解釈する経路は作らない (トラバーサル・YAML 再読み込みの穴を防ぐ)

### 出力配置: アンカーパス = 出力アドレス

各 edition ルート直下の予約名前空間 `blob/` 以下に、blob ノードのアンカーパス (`/blob/<id>`) をそのまま出力パスとしてミラーする。**アンカーパス = 出力アドレス** にすることで、リンク解決 (href が blob ノードのアンカーパスを指す) と出力配置が一致する — contents 相対パスを edition ルート直下へ直接置く旧案だと両者がずれる。`/blob/` は予約名前空間でテンプレート由来のページパスが入らないため、blob 出力パスがページパスと**構造的に衝突しえない** (衝突検査は不要)。

## Internal Design

### normalize の出力では contents 相対パスのまま置く

normalize は blob のバイト列を出力 data ツリーに contents 相対パスのまま (`data/contents/<id>`) ミラーする。レコードファイルは元の名前に `.json` を追記した名前になるので、レコード形式の拡張子 (YAML / JSON / Markdown) を持ちえない blob とは構造的に衝突せず、blob 用の名前空間を切る必要がない。以降は他のファイルと同じ経路で下流へ運ばれる（[運搬機構](../40-communication/index.md#運搬機構)）。
