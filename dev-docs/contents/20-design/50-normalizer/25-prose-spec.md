# Prose

散文（prose）は `contents/` 配下の Markdown で、内蔵コレクション `prose` のレコードになる（一ファイル一レコード）。レコードの形は `docs/reference/schema.md` の prose 節が約束し、本章はその項目ごとに設計判断を置く。Markdown のパース（相対リンクの `node:` 正規化・見出し抽出）は [Markdown Parser Specification](30-markdown-parser-spec.md) を参照。

## External Design

### `id` — ファイルパス由来で、読む順もここに符号化する

id は `contents_dir` からの相対パス（拡張子なし）そのもの。読む順は id の文字列順で決まり、フォルダの `index` がその配下に先行する。順序を表す別チャネル（front-matter、toc）は持たない。したがって順序はファイル名で表す——ゼロ埋め・隙間空き番号 prefix（`10-architecture.md`。フォルダの `index` には振らない）はその一つの運用で、dev-docs がそう使っている。id の安定（並べ替えで `node:` リンクが壊れない）を捨て、順序の可視性と id の住所性を取る判断。[背景](../../90-appendix/20-design/50-normalizer/25-prose-spec.md#三すくみどれか一つを必ず捨てる)と[却下した代替案](../../90-appendix/20-design/50-normalizer/25-prose-spec.md#却下した代替案蒸し返し防止)。

### `title` — first H1 由来

表示タイトルは本文の最初の H1 から導出し、H1 が無ければ持たない。ファイル名（番号 prefix を含む）は id / URL にのみ現れ、タイトルには出ない。

### `order_key` / `depth` — 導出はレコード、ソートはテンプレート

各レコードは `order_key`（文字列順で folder-preorder になるキー。フォルダの `index` がその配下に先行する）と `depth`（フォルダ木での見出しレベル）を持つ。両者は id のみの純導出なので preprocess がレコード単位で付けられるが、ソートは collection が揃わないとできないので、テンプレート側（`sort(attribute="order_key")`）に置く。フォルダ木を見出しの入れ子として一冊に綴じる使い方（dev-docs の book edition）は、この二つと `under_heading` だけで書ける。

### `headings` — リンクの着地点

本文の見出しを `{id, title, level}` のフラットなリストとして持つ。セクション単位のレコードは作らず、id は見出しテキストの GitHub 互換 slug、参照の妥当性は Generate で見る。設計は [見出し抽出](30-markdown-parser-spec.md#見出し抽出)。

### `content` — ソースそのまま、相対リンクだけ `node:` 化

本文は H1 を含むファイル全体。contents 内に解決する相対リンクだけを `node:` 記法に書き換え、他は書かれたとおりに保つ。設計は [リンク正規化](30-markdown-parser-spec.md#リンク正規化)。

### `mime_type` — `text/markdown`

blob と同じ位置に持ち、body で包まない（[blob のレコード形状](27-blob-spec.md#レコード形状の判断)）。
