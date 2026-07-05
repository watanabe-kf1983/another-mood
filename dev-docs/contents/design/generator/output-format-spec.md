# Output Format Specification

テンプレートエンジンの出力フォーマット (Markdown / HTML / Mermaid 等) ごとに escape 関数と位置依存ヘルパを切り替える仕組みの仕様。

利用者向けの API 仕様 (`md_escape` の振る舞い・4 ヘルパの使い方) は `docs/reference/template.md` を参照。本仕様は設計判断と内部構造に絞る。

## External Design

### 課題

テンプレートエンジンに出力フォーマット別の escape 機構が無いと、ユーザ入力に出力フォーマットの特殊文字 (Markdown なら `*` `_` `|` `` ` `` `<` 等) が混じった瞬間に出力が壊れる。Jinja2 標準の `autoescape` は HTML escape 決め打ちで、Markdown / Mermaid / AsciiDoc / SQL 等の非 HTML フォーマットに直接は使えない。

複数フォーマットを並行サポートしつつ、フォーマット別の escape をテンプレート著者の書き忘れに頼らず保証できる機構が要る。

### Escape 方針: ASCII punctuation 一律 backslash escape

`md` output_format の地の文 escape (`md_escape`) は CommonMark spec の許容範囲 (任意の ASCII punctuation は `\` で escape 可能) に乗せて、全 ASCII punctuation を一律に backslash escape する。

```python
def md_escape(text: str) -> str:
    return re.sub(r'([!-/:-@\[-`{-~])', r'\\\1', text)
```

選んだ理由:

- **網羅的安全性**: 見出し / リスト / 引用 / Thematic break / 表セル / 強調 / inline code / 生 HTML タグ / 既存 escape / HTML entity の全構文記号を 1 ルールで防げる。「想定外の入力で崩れる」事故が起きない
- **レンダリング上の副作用なし**: CommonMark の backslash escape は表示上は escape 前と同じになるため、不要な escape が混じっても出力品質が落ちない
- **実装の単純性**: 「文脈別に必要最小限の escape を行う」方式は安全だが、文脈判定が複雑になり保守コストが高い

### 位置依存ヘルパの 2 分類

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

`<projectDir>/filters.py` の auto-load や entry points 経由でプロジェクト固有の Python ヘルパを登録する仕組みは **意図的にサポートしない**。

ソース (Another Mood プロジェクト) を書いた人とそのソースでツールを動かす人が一致するとは限らない。任意 Python の実行を許すと、配布されたプロジェクトを `mood build` した時点で第三者の手元で任意コードが走る。これは Excel マクロウィルスと同型の問題で、被害は受け取り側に発生する。

整形ニーズは Jinja2 標準フィルタ + 本仕様の位置依存ヘルパ + [system filters](#outputformat-と-system-filters-の住み分け) (built-in メタ用、ユーザ非公開) で吸収する。これらで足りないケースが顕在化したら、Python 任意実行を経由しない手段 (宣言的 DSL の拡張、データ側での事前整形 等) で詰める。

## Internal Design

### finalize-based escape の選択

Jinja2 の autoescape は `markupsafe.escape` (HTML escape) に決め打ちで escape 関数差し替え API が無い。output_format ごとに escape を切り替えるため、`autoescape=False` のまま `finalize` フックで `output_format.escape(str(value))` を適用する方式を採る。

コードを読んで `finalize=_finalize` を見ても理由は復元できないため、保守時に「autoescape に戻したい」誘惑に乗らないようここに残す。

### Markup 返却契約

`finalize` は `Markup` を素通しする。ヘルパは **`Markup` を返したら、そのヘルパが内部のあらゆる escape を完了させていなければならない**。契約違反のヘルパはセーフネットを素通って崩れた出力を出す。

新しい位置依存ヘルパを追加する際の不変条件。各ヘルパの具体的な実装責務 (CommonMark 6.1 制約、padding 規則、safe-set 等) は `md.py` の docstring と `test_md.py` で担保する。

### OutputFormat と meta-template filters の住み分け

OutputFormat 記述子の `globals` / `filters` は **「出力フォーマット固有の位置依存正規化」** のためだけに使う。built-in メタテンプレートが必要とする補助関数 (catalog データへの dotted-key access、parent_entity 連鎖 descent、YAML ダンプ) はフォーマット非依存・位置非依存でメタテンプレート専用のドメインヘルパなので、`OutputFormat` ではなく `meta_templates.py` に `META_TEMPLATES_FILTERS` として持ち、メタテンプレート描画時のみ `TemplateEngine` の `filters` 引数で注入する。

新しい補助関数を追加する際の判定:

- フォーマット固有 (位置依存正規化) → OutputFormat
- メタテンプレート固有 (catalog 走査・整形) → META_TEMPLATES_FILTERS

境界を曖昧にして OutputFormat にメタ専用 filter を混ぜると、将来 output_format を追加するたびに同じ filter を再登録する DRY 違反になり、メタテンプレートの依存をユーザテンプレートにも漏らしてしまう。

### config 依存フィルタとフォーマットの注入

`globals` / `filters` は config 非依存の静的ヘルパだが、source ページ相対のリンクフィルタ (`href` / `link`、[generator.md#リンク解決](generator.md#リンク解決)) は paging 設定 (`Edition`) に依存する。これらは `OutputFormat.link_filters` を「`Edition` を受けてフィルタ群を返す factory」フィールドとして持たせ、`make_environment(output_format, edition)` がビルドの config で呼んで登録する。こうしてフォーマットは自分のフィルタ面全体（静的 + config 依存）を一箇所で所有し、呼び出し側が個別に配線せずに済む。

`make_environment` / `TemplateEngine` は使う `OutputFormat` を **注入で受け取る**（具象フォーマットを import しない）。汎用エンジンが具象フォーマットを名指しすると `template_engine → md` の循環依存になるため、フォーマットの選択は合成点 (Generator) に寄せる。

### mood_view サブテンプレートの output_format 解決

`{% mood_view "template.md" with data %}` でサブテンプレートを呼ぶ場合、`template_name` の拡張子から output_format を引き、対応する Environment で render する想定。テンプレート参照に拡張子が含まれていることは [template-spec.md](template-spec.md#テンプレート参照の拡張子明示化-p2) の前提に依存。

現状は MD output_format に決め打ち。複数 output_format を扱うテンプレートが登場した時に実装する制約として記録しておく。

## Proposals

以下は本仕様では扱わない。実際にニーズが顕在化した時点で別仕様として詰める:

- **CommonMark の他の位置依存正規化** — indented code block、link title、autolink 等。実需が顕在化したら 4 ヘルパと同じ枠組みで追加する
- **Typed Value 機構** — 値が `mime_type` (例: `text/markdown`) と `content` を持つオブジェクトで、テンプレート側がスキーマに頼らず値自体を見て escape をバイパスする発想。汎用性は高いが、素 string 主体の入力形式では運用負荷が見合わない
- **`md` 以外の output_format の具体仕様** — `html` / `adoc` / `sql` / `mermaid` の escape 関数とラッパーフィルタ。各 output_format を扱うテンプレートを実際に導入する段階で詰める
- **入れ子 output_format** — FreeMarker の `XML{HTML}` のような「外側 XML / 内側 HTML で二重 escape」の表現。Markdown 内の Mermaid fence のような実需はあるが、単一フォーマットで動く基盤を確立した後に検討する
- **ブロック単位の output_format 切替構文** — Twig の `{% autoescape 'js' %}` 相当。テンプレート内で部分的にフォーマットを切り替える独自タグ。入れ子 output_format と同じ理由で後送り
- **anchor 系フィルタの escape** — [anchor-spec.md](anchor-spec.md) の percent-encoding 規則。アンカー実装と一緒に詰める
