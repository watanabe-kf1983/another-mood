# Template Specification

## External Design

### 言語のスコープ

#### テンプレートの語彙は filter / test / operator に限る

値そのものはメソッドを持たない。minijinja の `pycompat` は Python の文字列 / list / dict メソッドを値に生やすが、これを切っている（`.startswith()` は空描画ではなくメソッド名つきのエラー）。理由は利用者に案内できる境界が引けること（[背景](../../90-appendix/20-design/70-generator/20-template-spec.md#語彙を-filter--test--operator-に閉じる理由)）。

#### ユーザ提供 Python ヘルパは受け付けない

`<projectDir>/filters.py` の auto-load や entry points 経由でsbdb プロジェクト固有の Python ヘルパを登録する仕組みは **意図的にサポートしない**。

ソース（sbdb プロジェクト）を書いた人とそのソースでツールを動かす人が一致するとは限らない。任意 Python の実行を許すと、配布されたsbdb プロジェクトを `mood build` した時点で第三者の手元で任意コードが走る。これは Excel マクロウィルスと同型の問題で、被害は受け取り側に発生する。この「著者 ≠ 実行者」の信頼境界と、テンプレート実行そのものの扱いは [template-trust-model.md](25-template-trust-model.md) に一般化して整理している。

整形ニーズは Jinja2 標準フィルタ + 本仕様の位置依存ヘルパ + meta-template filters (built-in メタ用、ユーザ非公開。`meta_templates.py` の `META_TEMPLATES_FILTERS`) で吸収する。これらで足りないケースが顕在化したら、Python 任意実行を経由しない手段 (宣言的 DSL の拡張、データ側での事前整形 等) で詰める。

### 言語の意味論

#### undefined アクセスの扱い

本プロジェクトは minijinja の `undefined_behavior` に `chainable` を明示指定する（既定のままでは `{{ x.a }}` がエラーになる。[背景](../../90-appendix/20-design/70-generator/20-template-spec.md#なぜ-undefined-アクセスをエラーにしないか)）。

#### 欠損値は何も描かない

欠損した値をテンプレートが描こうとしたとき、出力は空になる。フィルタや関数を通した場合も同じで、ヘルパーが `"None"` のような表現を発明することはない。この規則があるので [10-json-data-model.md](../40-communication/10-json-data-model.md#配列内オブジェクトのフィールド統一) の「nullable な項目は値ではなくフィールドごと省略する」規約が成り立つ。

**欠損と「壊れた参照」は別に扱う。** 解決を試みて外した参照（missing node）は目立つ `[text]` を出す（[未解決参照の扱い](30-anchor-spec.md#未解決参照の扱い)）。一方 optional フィールドの欠損は上の規約が認めている正常系なので、目立たせず何も描かない。外した案は[背景](../../90-appendix/20-design/70-generator/20-template-spec.md#欠損の描画で外した-2-案)。

### 出力フォーマット

テンプレートエンジンの出力フォーマット (Markdown / HTML / Mermaid 等) ごとに escape 関数と位置依存ヘルパを切り替える仕組みの仕様（[課題](../../90-appendix/20-design/70-generator/20-template-spec.md#出力フォーマットの課題)）。

利用者向けの API 仕様 (`md_escape` の振る舞い・位置依存ヘルパの使い方) は `docs/reference/template.md` を参照。本仕様は設計判断と内部構造に絞る。

#### Escape 方針: ASCII punctuation 一律 backslash escape

`md` output_format の地の文 escape (`md_escape`) は CommonMark spec の許容範囲 (任意の ASCII punctuation は `\` で escape 可能) に乗せて、全 ASCII punctuation を一律に backslash escape する。1 ルールで全構文記号を防ぎ、backslash escape は表示を変えないので過剰に escape しても害がない（[背景](../../90-appendix/20-design/70-generator/20-template-spec.md#escape-方針を-ascii-punctuation-一律にした理由)）。

### 内蔵ヘルパ

Jinja2 標準に加えて本ツールが定義する filter / 関数。リンク系（`node` / `link` / `href` / `anchor` / `relink` / `child` / `label`）は [anchor-spec.md のテンプレートからの参照](30-anchor-spec.md#テンプレートからの参照) が扱う。

#### render とサブテンプレート

`render` フィルタは、主題をサブテンプレートで描く手段。`{{ subject | render("template.md") }}` と書くと、主題の型が edition の `file_per` にあればそのノードを別ページとして書き出し、無ければその場に inline 展開する。root テンプレート（`index.md`）から始まり、`render` で子ノードに降りていくことで、データツリーの形に沿ったページ群ができる。Jinja2 の `{% include %}` が呼び出し側の context を共有するのに対し、サブテンプレートには主題だけが渡る。主題は `this` に束縛し、map ならフィールドも裸の変数に展開する。root テンプレートも同じ規則で、主題はツリーの root（利用者向けの規則は `docs/reference/template.md` の Template context と Subtemplate side）。フィルタの仕様（戻り値、出力パス、サブテンプレート側の書き方）は `docs/reference/template.md` の `render`、どのノードがページになるかの規則は [anchor-spec.md のページ分割](30-anchor-spec.md#ページ分割)。

#### 位置依存ヘルパの 2 分類

`md_escape` (finalize) は「地の文」位置でしか正しくない。inline code span / fenced code block / 表セル / link URL では文脈依存の正規化が必要。これらは以下の 2 形態で提供する:

- **ビルダ関数** (`code_inline` / `code_fenced`) — 構文単位そのものを構築する。delimiter 幅を中身に応じて動的に決める必要があり、テンプレ著者が固定数の `` ` `` を書くと任意入力で破綻するため、関数として提供
- **transform フィルタ** (`in_cell` / `as_url`) — delimiter 自体はテンプレ著者が書き、内側に入れる値を位置に応じて正規化する

ビルダ系を関数、transform 系を filter にする住み分けは Jinja2 idiom (`range` / `dict` / `lipsum` 等の構築系は global function、`upper` / `urlencode` / `tojson` 等の変換系は filter) に整合する。
#### 命名のフォーマット中立性

`code_*` / `in_*` / `as_*` は **位置概念** を指す名前であり、フォーマットに依存しない。同じ位置概念は他フォーマット (HTML 等) にも存在し、output_format ごとに同名で別実装を登録できる:

| ヘルパ | md 実装 | html 実装 (将来例) |
|---|---|---|
| `code_inline(x)` | backtick 動的調整 | `<code>{html_escape(x)}</code>` |
| `code_fenced(x, lang)` | fence 動的調整 | `<pre><code class="language-{lang}">{html_escape(x)}</code></pre>` |
| `x \| in_cell` | `\n`→`<br>` + escape | HTML escape のみ |
| `x \| as_url` | URL encode + `()` escape | HTML attr escape + URL encode |

将来 HTML 等の output_format を追加する際に、テンプレート著者は同じ呼び口で書けばフォーマット切替時の書き換えコストが発生しない。

## Proposals

以下は本仕様では扱わない。実際にニーズが顕在化した時点で別仕様として詰める:

- **CommonMark の他の位置依存正規化** — indented code block、link title、autolink 等。実需が顕在化したら既存ヘルパと同じ枠組みで追加する
- **Prose 型に的を絞った mime_type 多態** — text/markdown 以外の prose (text/html をページとして解釈する等) を、レコード直下の `mime_type` を分岐キーに扱う機構。かつて「Typed Value 機構」(値が `mime_type` と `content` を持ち、テンプレートがスキーマに頼らず値自体を見て振る舞いを変える汎用の発想) として検討したが、一般機構としては採らない — ユーザデータに厳密な型を宣言させることがこのツールのアイデンティティであり、スキーマ非依存の値検査はそれと矛盾する。多態を要求しうるのは組み込みコレクション (prose / blob) に限られ、型はレコード直下の `mime_type` (envelope のヘッダ相当、[blob-spec.md](../50-normalizer/27-blob-spec.md#レコード形状の判断) 参照) が持つ。機構はその布石の上に、実需が顕在化した時点で Prose 型特化として詰める
- **`md` 以外の output_format の具体仕様** — `html` / `adoc` / `sql` / `mermaid` の escape 関数とラッパーフィルタ。各 output_format を扱うテンプレートを実際に導入する段階で詰める
- **render サブテンプレートの output_format 解決** — `subject | render("template.md")` でサブテンプレートを呼ぶ場合、`template_name` の拡張子から output_format を引き、対応する Environment で render する想定。テンプレート参照に拡張子が含まれていること（利用者向け仕様は `docs/reference/template.md` の render）に依存する。現状は MD output_format に決め打ち。複数 output_format を扱うテンプレートが登場した時に実装する制約として記録しておく
- **入れ子 output_format** — FreeMarker の `XML{HTML}` のような「外側 XML / 内側 HTML で二重 escape」の表現。Markdown 内の Mermaid fence のような実需はあるが、単一フォーマットで動く基盤を確立した後に検討する
- **ブロック単位の output_format 切替構文** — Twig の `{% autoescape 'js' %}` 相当。テンプレート内で部分的にフォーマットを切り替える独自タグ。入れ子 output_format と同じ理由で後送り
