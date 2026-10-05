# Output Format Specification

テンプレートエンジンの出力フォーマット (Markdown / HTML / Mermaid 等) ごとに escape 関数と位置依存ヘルパを切り替える仕組みの仕様。

利用者向けの API 仕様 (`md_escape` の振る舞い・位置依存ヘルパの使い方) は `docs/reference/template.md` を参照。本仕様は設計判断と内部構造に絞る。

## External Design

### 課題

> **[W4 → appendix?]** 推奨: 移す

テンプレートエンジンに出力フォーマット別の escape 機構が無いと、ユーザ入力に出力フォーマットの特殊文字 (Markdown なら `*` `_` `|` `` ` `` `<` 等) が混じった瞬間に出力が壊れる。Jinja2 標準の `autoescape` は HTML escape 決め打ちで、Markdown / Mermaid / AsciiDoc / SQL 等の非 HTML フォーマットに直接は使えない。

複数フォーマットを並行サポートしつつ、フォーマット別の escape をテンプレート著者の書き忘れに頼らず保証できる機構が要る。

### Escape 方針: ASCII punctuation 一律 backslash escape

> **[W4 dup]** ↔ md.py:34-37,46-47 (正規表現込み) (a)、template.md:401-423 (b) — 完全。案?: 方針と理由 3 点は設計判断→残す。コード断片は削除→コード

`md` output_format の地の文 escape (`md_escape`) は CommonMark spec の許容範囲 (任意の ASCII punctuation は `\` で escape 可能) に乗せて、全 ASCII punctuation を一律に backslash escape する。

```python
def md_escape(text: str) -> str:
    return re.sub(r"([!-/:-@\[-`{-~])", r"\\\1", text)
```

選んだ理由:

- **網羅的安全性**: 見出し / リスト / 引用 / Thematic break / 表セル / 強調 / inline code / 生 HTML タグ / 既存 escape / HTML entity の全構文記号を 1 ルールで防げる。「想定外の入力で崩れる」事故が起きない
- **レンダリング上の副作用なし**: CommonMark の backslash escape は表示上は escape 前と同じになるため、不要な escape が混じっても出力品質が落ちない
- **実装の単純性**: 「文脈別に必要最小限の escape を行う」方式は安全だが、文脈判定が複雑になり保守コストが高い

### 位置依存ヘルパの 2 分類

> **[W4 dup]** ↔ template.md:455-466 (b)、md.py:50-73 (a) — 部分。案: 残す

`md_escape` (finalize) は「地の文」位置でしか正しくない。inline code span / fenced code block / 表セル / link URL では文脈依存の正規化が必要。これらは以下の 2 形態で提供する:

- **ビルダ関数** (`code_inline` / `code_fenced`) — 構文単位そのものを構築する。delimiter 幅を中身に応じて動的に決める必要があり、テンプレ著者が固定数の `` ` `` を書くと任意入力で破綻するため、関数として提供
- **transform フィルタ** (`in_cell` / `as_url`) — delimiter 自体はテンプレ著者が書き、内側に入れる値を位置に応じて正規化する

ビルダ系を関数、transform 系を filter にする住み分けは Jinja2 idiom (`range` / `dict` / `lipsum` 等の構築系は global function、`upper` / `urlencode` / `tojson` 等の変換系は filter) に整合する。

### 命名のフォーマット中立性

`code_*` / `in_*` / `as_*` は **位置概念** を指す名前であり、フォーマットに依存しない。同じ位置概念は他フォーマット (HTML 等) にも存在し、output_format ごとに同名で別実装を登録できる:

| ヘルパ | md 実装 | html 実装 (将来例) |
|---|---|---|
| `code_inline(x)` | backtick 動的調整 | `<code>{html_escape(x)}</code>` |
| `code_fenced(x, lang)` | fence 動的調整 | `<pre><code class="language-{lang}">{html_escape(x)}</code></pre>` |
| `x \| in_cell` | `\n`→`<br>` + escape | HTML escape のみ |
| `x \| as_url` | URL encode + `()` escape | HTML attr escape + URL encode |

将来 HTML 等の output_format を追加する際に、テンプレート著者は同じ呼び口で書けばフォーマット切替時の書き換えコストが発生しない。

### ユーザ提供 Python ヘルパは受け付けない

> **[W4 dup]** ↔ 60-template-trust-model:9-15,49-54 (c, 部分)。案: 残す (具体的な却下対象はここのみ)

`<projectDir>/filters.py` の auto-load や entry points 経由でプロジェクト固有の Python ヘルパを登録する仕組みは **意図的にサポートしない**。

ソース (Another Mood プロジェクト) を書いた人とそのソースでツールを動かす人が一致するとは限らない。任意 Python の実行を許すと、配布されたプロジェクトを `mood build` した時点で第三者の手元で任意コードが走る。これは Excel マクロウィルスと同型の問題で、被害は受け取り側に発生する。この「著者 ≠ 実行者」の信頼境界と、テンプレート実行そのものの扱いは [template-trust-model.md](60-template-trust-model.md) に一般化して整理している。

整形ニーズは Jinja2 標準フィルタ + 本仕様の位置依存ヘルパ + [meta-template filters](#outputformat-と-meta-template-filters-の住み分け) (built-in メタ用、ユーザ非公開) で吸収する。これらで足りないケースが顕在化したら、Python 任意実行を経由しない手段 (宣言的 DSL の拡張、データ側での事前整形 等) で詰める。

## Internal Design

### finalize-based escape の選択

> **[W4 dup]** ↔ template_engine.py:53-60,73-76 make_environment コメント (理由まで) (a, 完全)。注意: 「コードを読んでも理由は復元できない」は古い。案?: 設計判断→design に残し、コードのコメントを縮める。逆 (コード正本、ここは削除) も可

エンジンの auto-escape は HTML escape 決め打ちで、escape 関数の差し替え口が無い（minijinja はテンプレート名の拡張子で有効化を決める）。output_format ごとに escape を切り替えるため、auto-escape を `auto_escape_callback` で無条件に切り、`finalizer` フックで `output_format.escape(str(value))` を適用する方式を採る。

コードを読んで `finalizer=_finalize` を見ても理由は復元できないため、保守時に「auto-escape に戻したい」誘惑に乗らないようここに残す。

### Markup 返却契約

> **[W4 dup]** ↔ md.py 各ヘルパコメント、render_processor.py:73-75 (a, 部分)。案: 残す (不変条件の一般化はここのみ)

`finalize` は `Markup` を素通しする。ヘルパは **`Markup` を返したら、そのヘルパが内部のあらゆる escape を完了させていなければならない**。契約違反のヘルパはセーフネットを素通って崩れた出力を出す。

新しい位置依存ヘルパを追加する際の不変条件。各ヘルパの具体的な実装責務 (CommonMark 6.1 制約、padding 規則、safe-set 等) は `md.py` のコメントと `test_md.py` で担保する。

### OutputFormat と meta-template filters の住み分け

> **[W4 dup]** ↔ meta_templates.py:4,126-135、md.py:263-264 (a, 部分)。案: 残す

`md.py` のモジュール定数 `MD_GLOBALS` / `MD_FILTERS` は **「出力フォーマット固有の位置依存正規化」** のためだけに使う。built-in メタテンプレートが必要とする補助関数 (catalog データへの dotted-key access、parent_entity 連鎖 descent、YAML ダンプ、ノードのアンカーパス取り出し) はフォーマット非依存・位置非依存でメタテンプレート専用のドメインヘルパなので、`meta_templates.py` に `META_TEMPLATES_FILTERS` として持ち、メタ edition の `extra_filters` としてのみ注入する。

新しい補助関数を追加する際の判定:

- フォーマット固有 (位置依存正規化) → `MD_GLOBALS` / `MD_FILTERS`
- メタテンプレート固有 (catalog 走査・整形) → META_TEMPLATES_FILTERS

境界を曖昧にしてフォーマット側にメタ専用 filter を混ぜると、将来 output_format を追加するたびに同じ filter を再登録する DRY 違反になり、メタテンプレートの依存をユーザテンプレートにも漏らしてしまう。

### ヘルパの配線とフォーマットの注入

> **[W4 dup]** ↔ template_engine.py:31-33,62-64 OutputFormat docstring、generator.py:186-225 (a, 完全)。案?: 構造の一文 (注入、エンジンはヘルパを登録しない) は残す。docstring と重なる説明は削除

`OutputFormat` が持つのは render policy（escape 関数・ブロック空白制御・`post_process`）だけで、ヘルパは policy ではない。フォーマットの静的ヘルパ (`MD_GLOBALS` / `MD_FILTERS`) も、paging と node map に束縛されるリンクフィルタ (`make_link_filters(paging, node_map)`、[generator.md#リンク解決](10-generator.md#リンク解決)) も、合成点である Generator が edition ごとに組み立てて `TemplateEngine` の `filters` / `globals` に渡す。エンジン自身はヘルパを一つも登録しない。

`make_environment` / `TemplateEngine` は使う `OutputFormat` を **注入で受け取る**（具象フォーマットを import しない）。汎用エンジンが具象フォーマットを名指しすると `template_engine → md` の循環依存になるため、フォーマットの選択は合成点 (Generator) に寄せる。

### render サブテンプレートの output_format 解決

`subject | render("template.md")` でサブテンプレートを呼ぶ場合、`template_name` の拡張子から output_format を引き、対応する Environment で render する想定。テンプレート参照に拡張子が含まれていること（利用者向け仕様は `docs/reference/template.md` の render）に依存する。

現状は MD output_format に決め打ち。複数 output_format を扱うテンプレートが登場した時に実装する制約として記録しておく。

## Proposals

以下は本仕様では扱わない。実際にニーズが顕在化した時点で別仕様として詰める:

- **CommonMark の他の位置依存正規化** — indented code block、link title、autolink 等。実需が顕在化したら既存ヘルパと同じ枠組みで追加する
- **Prose 型に的を絞った mime_type 多態** — text/markdown 以外の prose (text/html をページとして解釈する等) を、レコード直下の `mime_type` を分岐キーに扱う機構。かつて「Typed Value 機構」(値が `mime_type` と `content` を持ち、テンプレートがスキーマに頼らず値自体を見て振る舞いを変える汎用の発想) として検討したが、一般機構としては採らない — ユーザデータに厳密な型を宣言させることがこのツールのアイデンティティであり、スキーマ非依存の値検査はそれと矛盾する。多態を要求しうるのは組み込みコレクション (prose / blob) に限られ、型はレコード直下の `mime_type` (envelope のヘッダ相当、[blob-spec.md](../40-communication/30-blob-spec.md#レコード形状の判断) 参照) が持つ。機構はその布石の上に、実需が顕在化した時点で Prose 型特化として詰める
- **`md` 以外の output_format の具体仕様** — `html` / `adoc` / `sql` / `mermaid` の escape 関数とラッパーフィルタ。各 output_format を扱うテンプレートを実際に導入する段階で詰める
- **入れ子 output_format** — FreeMarker の `XML{HTML}` のような「外側 XML / 内側 HTML で二重 escape」の表現。Markdown 内の Mermaid fence のような実需はあるが、単一フォーマットで動く基盤を確立した後に検討する
- **ブロック単位の output_format 切替構文** — Twig の `{% autoescape 'js' %}` 相当。テンプレート内で部分的にフォーマットを切り替える独自タグ。入れ子 output_format と同じ理由で後送り
