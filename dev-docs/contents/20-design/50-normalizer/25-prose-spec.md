# Prose

散文（prose）は `contents/` 配下の Markdown で、内蔵コレクション `prose` のレコードになる（一ファイル一レコード）。レコードの形は `docs/reference/schema.md` の prose 節が約束し、本章はその項目ごとに設計判断を置く。Markdown のパーサは [Normalizer](10-normalizer.md#markdown-は-markdown-it-py-で読む)。

## External Design

### `id` — ファイルパス由来で、読む順もここに符号化する

id は `contents_dir` からの相対パス（拡張子なし）そのもの。読む順は id の文字列順で決まり、フォルダの `index` がその配下に先行する。順序を表す別チャネル（front-matter、toc）は持たない。したがって順序はファイル名で表す——ゼロ埋め・隙間空き番号 prefix（`10-architecture.md`。フォルダの `index` には振らない）はその一つの運用で、dev-docs がそう使っている。id の安定（並べ替えで `node:` リンクが壊れない）を捨て、順序の可視性と id の住所性を取る判断。[背景](../../90-appendix/20-design/50-normalizer/25-prose-spec.md#三すくみどれか一つを必ず捨てる)と[却下した代替案](../../90-appendix/20-design/50-normalizer/25-prose-spec.md#却下した代替案蒸し返し防止)。

### `title` — first H1 由来

表示タイトルは本文の最初の H1 から導出し、H1 が無ければ持たない。ファイル名（番号 prefix を含む）は id / URL にのみ現れ、タイトルには出ない。

### `order_key` / `depth` — 導出はレコード、ソートはテンプレート

各レコードは `order_key`（文字列順で folder-preorder になるキー。フォルダの `index` がその配下に先行する）と `depth`（フォルダ木での見出しレベル）を持つ。両者は id のみの純導出なので preprocess がレコード単位で付けられるが、ソートは collection が揃わないとできないので、テンプレート側（`sort(attribute="order_key")`）に置く。フォルダ木を見出しの入れ子として一冊に綴じる使い方（dev-docs の book edition）は、この二つと `under_heading` だけで書ける。

### `headings` — リンクの着地点

本文の見出しを **リンクの着地点** として `{id, title, level}` のフラットなリストに materialize する。見出しが持つのは住所メタデータだけで、本文 (`content`) は一度しか現れない。

id は **見出しテキストから導出する GitHub 互換 slug**（`## API の設計` → `api-の設計`）。見出しリンクが我々の Hugo 出力・GitHub・VS Code preview のいずれでも同じ id に着地させるためで、規則の正本と実装参照は `github_slug` の docstring。id の安定は「不変であること」ではなく **「壊れた参照は必ずビルドで報告される」** で担保する。

見出しへの参照は **ドキュメント間のクロスリンク** なので、妥当性は normalize の参照整合性検査ではなく **Generate フェーズのリンク解決** で見る（[未解決参照の扱い](../70-generator/20-anchor-spec.md#未解決参照の扱い)）。

見出しがリンクの宛先としてどう住所を持つかは [anchor-spec.md の Prose の例外](../70-generator/20-anchor-spec.md#prose-の例外)。却下した代替案は[背景](../../90-appendix/20-design/50-normalizer/25-prose-spec.md#見出しの却下した代替案)。

### `content` — ソースそのまま、相対リンクだけ `node:` 化

本文は H1 を含むファイル全体。contents 内に解決する相対リンクだけを `node:` アンカーパス記法（インラインリンク形）に書き換え、他は書かれたとおりに保つ。変換規則は `docs/reference/schema.md` の prose 節、例は [anchor-spec.md の Markdown 本文中のアンカー参照](../70-generator/20-anchor-spec.md#markdown-本文中のアンカー参照)。`.md` 以外のターゲットは `node:/blob/<id>` へ向け、[blob](27-blob-spec.md) 参照を prose のリンク正規化機構に相乗りさせる。

この書き換えは生成側フィルタ `relink`（`node:` → URL、[generator.md](../70-generator/10-generator.md#リンク解決)）の **逆向き処理**。解決はレキシカル（FS チェックなし）で、リンク先ノードの存在検証は relink（Generate フェーズ）に委ねる。

cross-doc リンクを全て `node:` 化する理由と、同一ページ内の純 `#frag` を恒久的に非変換とする理由は[背景](../../90-appendix/20-design/50-normalizer/25-prose-spec.md#cross-doc-リンクを全て-node-化する理由)。

### `mime_type` — `text/markdown`

blob と同じ位置に持ち、body で包まない（[blob のレコード形状](27-blob-spec.md#レコード形状の判断)）。
