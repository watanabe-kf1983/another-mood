# Output Format Specification

テンプレートエンジンの出力フォーマット (Markdown / HTML / Mermaid 等) ごとに escape 関数と位置依存ヘルパを切り替える仕組みの仕様。

## Proposals

> **未実装** — Phase 11 タスク [U1〜U4](../../../tasks.md)（U1: output_format モデル基盤 / U2: md escape / U3: md 位置依存ヘルパ / U4: 既存フィルタ移行）

### 課題

テンプレートエンジンに出力フォーマット別の escape 機構が無いと、ユーザ入力に出力フォーマットの特殊文字 (Markdown なら `*` `_` `|` `` ` `` `<` 等) が混じった瞬間に出力が壊れる。Jinja2 標準の `autoescape` は HTML escape 決め打ちで、Markdown / Mermaid / AsciiDoc / SQL 等の非 HTML フォーマットに直接は使えない。

複数フォーマットを並行サポートしつつ、フォーマット別の escape をテンプレート著者の書き忘れに頼らず保証できる機構が要る。

### 設計の骨格: output_format モデル

[Apache FreeMarker](https://freemarker.apache.org/docs/dgui_misc_autoescaping.html) の output_format 概念を参考にする。Python の主要テンプレートエンジン (Jinja2, Mako 等) は autoescape を HTML 決め打ちで設計しているため、複数フォーマット対応は自前で組む必要がある。複数フォーマットを一級市民にしている例としては FreeMarker (Java) と Twig (PHP) が挙げられる。

#### output_format 記述子

各 output_format は以下の四点セットで定義する:

- **`name`** — 識別子 (`md` / `html` / `mermaid` / `adoc` / `sql` …)
- **`escape`** — 素文字列を「そのフォーマットとして安全な文字列」に変換する関数
- **`globals`** — そのフォーマット専用のビルダ関数群 (後述。`env.globals` に登録)
- **`filters`** — そのフォーマット専用の transform フィルタ群 (後述。`env.filters` に登録)

#### 拡張子と output_format の対応

| 拡張子 | output_format |
|---|---|
| `.md`  | `md` |

他の拡張子 (`.html` / `.mermaid` / `.adoc` / `.sql` …) に対応する output_format は本仕様の対象外。

### `md` output_format の具体

#### escape 関数

**ASCII punctuation 一律 backslash escape**。CommonMark spec の許容範囲 (任意の ASCII punctuation は `\` で escape 可能) に乗る。

```python
def md_escape(text: str) -> str:
    return re.sub(r'([!-/:-@\[-`{-~])', r'\\\1', text)
```

これ 1 ルールで、以下の事故的構文解釈はすべて防げる:

- 行頭 `#` `-` `*` `+` `>` (見出し / リスト / 引用)
- `---` `***` (Thematic break) / Setext 見出し化
- リンクテキスト内の `[` `]`
- 表セル内の `|`
- 強調の `*` `_`
- 生 HTML タグの `<`
- inline code の `` ` ``
- escape character 自体の `\`
- HTML entity の `&`

レンダリング後の表示は元の文字のままなので副作用なし (CommonMark の backslash escape は表示上は escape 前と同じになる)。

#### Markdown 安全化ヘルパ

`md_escape` (finalize) は **「地の文」位置でしか正しくない**。CommonMark には地の文以外にも構文位置があり、各位置で安全な書き方が異なる。位置依存の処理が必要な場面のために以下のヘルパを提供する。

##### 文脈依存の正規化が必要な位置

| 位置 | 正規化の必要性 | ヘルパ |
|---|---|---|
| 地の文 | `md_escape` (finalize) で十分 | (なし、素 `{{ x }}`) |
| inline code span (`` `...` ``) | 中身の backtick run に応じて delimiter 幅を動的に変える必要 (CommonMark 6.1: code span 内で backslash escape は効かない) | `code_inline(x)` |
| fenced code block (` ```...``` `) | 中身の fence run に応じて fence 幅を動的に変える必要 | `code_fenced(x, lang)` |
| 表セル | `\n` を `<br>` 化、`|` の escape | `x \| in_cell` |
| link 構文の `(URL)` 部分 | URL encode + `(` `)` escape | `x \| as_url` |

##### ヘルパ性質の 2 分類

**ビルダ関数** — 構文単位そのものを構築する。delimiter 幅を中身に応じて動的に決める必要があり、テンプレ著者が固定数の `` ` `` / `` ``` `` を書くと任意入力で破綻するため、関数として提供する:

- `code_inline(value)` — value から inline code span を構築
- `code_fenced(value, language="")` — value と言語タグから fenced code block を構築

**文脈付き transform フィルタ** — delimiter 自体はテンプレ著者が書き、内側に入れる値を位置に応じて正規化する:

- `value | in_cell` — 表セル位置への埋め込み
- `value | as_url` — link 構文の URL 位置への埋め込み

ビルダ系を関数、transform 系を filter にする住み分けは Jinja2 の idiom (`range` / `dict` / `lipsum` 等の構築系は global function、`upper` / `urlencode` / `tojson` 等の変換系は filter) に整合する。

##### 命名のフォーマット中立性

`code_*` / `in_*` / `as_*` は **位置概念** を指す名前であり、フォーマットに依存しない。同じ位置概念は他フォーマット (HTML 等) にも存在し、output_format ごとに同名で別実装を登録できる:

| ヘルパ | md 実装 | html 実装 (将来例) |
|---|---|---|
| `code_inline(x)` | backtick 動的調整 | `<code>{html_escape(x)}</code>` |
| `code_fenced(x, lang)` | fence 動的調整 | `<pre><code class="language-{lang}">{html_escape(x)}</code></pre>` |
| `x \| in_cell` | `\n`→`<br>` + escape | HTML escape のみ |
| `x \| as_url` | URL encode + `()` escape | HTML attr escape + URL encode |

##### 提供形態

4 つとも `make_environment` 時に **`env.globals` / `env.filters` に自動登録** され、テンプレでは import なしで使える。Jinja2 ビルトイン (`range`, `dict`, `urlencode` 等) と同じ扱い。

##### 利用者向けの位置付け

利用者向けドキュメントでは、これらを「**常用必須の書き方ではなく、出力が崩れたときに引き出すエッジケース回避手段**」として案内する。デフォルトは素 `{{ x }}` で書けば良い (md_escape が地の文として安全化する) — 表セル内・コード span 内・URL 等の **特定位置で崩れが顕在化した時** に、対応するヘルパに reach する、というモデル。

built-in テンプレ内では予防的に利用する (任意入力に対する robustness を built-in 側で担保するため) が、利用者には reactive に紹介する。

### ヘルパの責務契約

ヘルパは **`Markup` を返したら、そのヘルパが内部のあらゆる escape を完了させていなければならない**。`finalize` (「実装方針」節参照) は `Markup` を素通しするため、ヘルパ実装が雑だとセーフネットを素通って崩れた出力が出る。

各ヘルパの責務:

- **`code_inline(value)`** — value 内の最長 backtick run `n` を見つけ、`n+1` (≥1) 個の backtick で囲む。value が backtick で始まる / 終わる、または全空白の場合は前後にスペース 1 を padding。escape は **入れない** (CommonMark 6.1: code span 内で `\` は literal、入れると逆に壊れる)。`Markup` 返却。
- **`code_fenced(value, language="")`** — value 内の最長 backtick run `n` を見つけ、`max(3, n+1)` 個の backtick で fence。中身の前後の改行を確保。escape は **入れない**。language は info string として opening fence 直後に出力。`Markup` 返却。
- **`value | in_cell`** — まず md_escape を内部適用 (`|` 等の表構造記号を escape)、次に `\n` を `<br>` (literal HTML) に置換。`Markup` 返却。※ Markup 返却で finalize がスキップされるため、escape の自前適用が必要。
- **`value | as_url`** — `urllib.parse.quote(safe="/?#[]@!$&'*+,;=~")` で encode し、追加で `(` `)` を `%28` `%29` に置換。`Markup` 返却。入力は **論理 URL** (URL-encode 前) を想定。これにより md_escape が URL 部分に backslash を混入するのを回避 (Hugo 等の renderer が backslash を `%5C` literal として percent-encode してしまう問題への対策)。

各ヘルパは「危ない入力 (backtick run / 改行 / `|` / URL 特殊文字 等) を入れても期待通りに動く」ことをテストで担保する。

### 実装方針

#### Environment はフォーマット別に factory 関数で生成

```python
@dataclass(frozen=True)
class OutputFormat:
    name: str
    escape: Callable[[str], str]
    filters: Mapping[str, Callable[..., Any]]

def make_environment(output_format: OutputFormat) -> Environment:
    def _finalize(value):
        if value is None or isinstance(value, Undefined):
            return ''
        if hasattr(value, '__html__'):  # Markup は素通し
            return str(value)
        return output_format.escape(str(value))

    env = Environment(
        # autoescape は使わない (Jinja2 標準は HTML escape 決め打ちのため)
        finalize=_finalize,
        ...
    )
    for name, func in output_format.filters.items():
        env.filters[name] = func
    return env
```

- `autoescape=False` (デフォルト) のまま、**`finalize` フックで素文字列に escape を適用**する。Jinja2 の autoescape 機構は `markupsafe.escape` (HTML escape) 決め打ちで、escape 関数の差し替え API が無いため。
- フィルタは **`Markup` を返す** ことで「escape 済み」を宣言する。`finalize` は `Markup` を素通しするので二重 escape にならない。
- `{% mood_view "template.md" with data %}` でサブテンプレートを呼ぶ場合は、`template_name` の拡張子から output_format を引き、対応する Environment で render する (テンプレート参照に拡張子が含まれていることは [template-spec.md](template-spec.md#テンプレート参照の拡張子明示化-p2) の前提に依存)。

#### テンプレート著者の書き口

```jinja2
{# .md テンプレートでは md 用 Environment が使われる #}

{{ user_name }}                                  {# md_escape が走る (ASCII punct backslash escape) #}
{{ raw_md_blob | safe }}                         {# safe で Markup 化 → 素通し #}

{# 任意入力を code として安全に埋める (ビルダ関数) #}
{{ code_inline(attribute.id) }}                  {# inline code span を構築 #}
{{ code_fenced(metadata | to_yaml, "yaml") }}    {# 言語タグ付き code block を構築 #}

{# 既存の構文 (表 / link) に埋める値の正規化 (transform フィルタ) #}
| col1 | {{ description | in_cell }} | ...
[label]({{ external_url | as_url }})
```

ヘルパは 4 つとも auto-available (import 不要)。

#### 既存フィルタの移行

[generator.py](../../../../src/another_mood/components/generator/generator.py) で登録している既存フィルタも output_format モデルに揃える (U4):

- `pluck`, `walk_entity` — 値取得系。Markup でなく素文字列を返す (= finalize で escape される)。フォーマット非依存。
- `to_yaml(flow=True)` — Markdown table cell 内に値をダンプする用途。任意入力に対する安全性は `to_yaml` の出力を `code_inline()` で wrap して担保する (`to_yaml` 自体はフォーマット非依存に保つ)。
- `mermaid_class_id` — Mermaid 識別子化。**Mermaid output_format 専用** のフィルタとして整理する (Mermaid テンプレート対応時)。

### 本仕様の対象外

以下は本仕様では扱わない。実際にニーズが顕在化した時点で別仕様として詰める:

- **ユーザ提供 Python ヘルパの登録ポイント** — プロジェクト固有の整形関数を利用者が追加で登録する仕組み (`<projectDir>/filters.py` auto-load、entry points 経由 等)。本仕様の 4 ヘルパは CommonMark の構文位置に対する「位置依存正規化」で集合が閉じるが、それ以外のプロジェクト固有処理 (entity 整形等) は別途検討する。
- **CommonMark の他の位置依存正規化** — indented code block、link title、autolink 等。実需が顕在化したら 4 ヘルパと同じ枠組みで追加する。
- **Typed Value 機構** — 値が `mime_type` (例: `text/markdown`) と `content` を持つオブジェクトで、テンプレート側がスキーマに頼らず値自体を見て escape をバイパスする発想。汎用性は高いが、素 string 主体の入力形式では運用負荷が見合わない。
- **`md` 以外の output_format の具体仕様** — `html` / `adoc` / `sql` / `mermaid` の escape 関数とラッパーフィルタ。各 output_format を扱うテンプレートを実際に導入する段階で詰める。
- **入れ子 output_format** — FreeMarker の `XML{HTML}` のような「外側 XML / 内側 HTML で二重 escape」の表現。Markdown 内の Mermaid fence のような実需はあるが、単一フォーマットで動く基盤を確立した後に検討する。
- **ブロック単位の output_format 切替構文** — Twig の `{% autoescape 'js' %}` 相当。テンプレート内で部分的にフォーマットを切り替える独自タグ。入れ子 output_format と同じ理由で後送り。
- **anchor 系フィルタの escape** — [anchor-spec.md](anchor-spec.md) の percent-encoding 規則。アンカー実装と一緒に詰める。
