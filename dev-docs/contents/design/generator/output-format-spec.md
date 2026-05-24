# Output Format Specification

テンプレートエンジンの出力フォーマット (Markdown / HTML / Mermaid 等) ごとに escape 関数とラッパーフィルタを切り替える仕組みの仕様。

## Proposals

> **未実装** — Phase 11 タスク [U1〜U4](../../../tasks.md)（U1: output_format モデル基盤 / U2: md escape / U3: md ラッパーフィルタ / U4: 既存フィルタ移行）

### 課題

テンプレートエンジンに出力フォーマット別の escape 機構が無いと、ユーザ入力に出力フォーマットの特殊文字 (Markdown なら `*` `_` `|` `` ` `` `<` 等) が混じった瞬間に出力が壊れる。Jinja2 標準の `autoescape` は HTML escape 決め打ちで、Markdown / Mermaid / AsciiDoc / SQL 等の非 HTML フォーマットに直接は使えない。

複数フォーマットを並行サポートしつつ、フォーマット別の escape をテンプレート著者の書き忘れに頼らず保証できる機構が要る。

### 設計の骨格: output_format モデル

[Apache FreeMarker](https://freemarker.apache.org/docs/dgui_misc_autoescaping.html) の output_format 概念を参考にする。Python の主要テンプレートエンジン (Jinja2, Mako 等) は autoescape を HTML 決め打ちで設計しているため、複数フォーマット対応は自前で組む必要がある。複数フォーマットを一級市民にしている例としては FreeMarker (Java) と Twig (PHP) が挙げられる。

#### output_format 記述子

各 output_format は以下の三点セットで定義する:

- **`name`** — 識別子 (`md` / `html` / `mermaid` / `adoc` / `sql` …)
- **`escape`** — 素文字列を「そのフォーマットとして安全な文字列」に変換する関数
- **`filters`** — そのフォーマット専用のラッパーフィルタ群 (後述)

#### 拡張子と output_format の対応

| 拡張子 | output_format |
|---|---|
| `.md`  | `md` |

他の拡張子 (`.html` / `.mermaid` / `.adoc` / `.sql` …) は対応する output_format を本仕様の対象外として定義する。

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

#### ラッパーフィルタ

無文脈 escape ではカバーできない**文脈依存ケース**は、専用フィルタで対処する:

| フィルタ名 (中立命名) | 用途 | やること |
|---|---|---|
| `inline_code` | inline code `` `...` `` 内への埋め込み | backtick 数を動的に長くする (escape は不要、内部で `\` は literal) |
| `fenced_code` | code fence ` ```...``` ` 内への埋め込み | fence 文字数を動的に長くする (escape は不要) |
| `table_cell` | 表セル内への埋め込み | 改行を `<br>` に変換 (一律 escape で `\|` 化は finalize 側で済む) |
| `link_url` | リンクの `(url)` 部分 | URL encoding (`%XX`) + `(` `)` escape |

フィルタ名はフォーマット中立にし、実装は output_format ごとに別物を登録する (「実装方針」節参照)。これにより `{{ value | inline_code }}` と書けば、その場のフォーマットに合わせて適切な escape が走る。

### ラッパーフィルタの責務契約

ラッパーフィルタは **`Markup` を返したら、そのフィルタが内部のあらゆる escape を完了させていなければならない**。`finalize` (「実装方針」節参照) は `Markup` を素通しするため、フィルタ実装が雑だとセーフネットを素通って崩れた出力が出る。

「何を escape するか」はフィルタごとに違うので、フィルタ仕様として明記する:

- `inline_code` / `fenced_code` — 内側は CommonMark で literal 扱い。**escape を入れたら逆に壊れる** (`\` が literal `\` として表示される)。fence 文字数の動的調整のみが仕事。
- `table_cell` — 内側は Markdown として解釈される。改行 → `<br>` 化が必須。`|` escape は `md_escape` (finalize) でカバーされるので追加処理不要。
- `link_url` — URL として解釈。URL encoding と `(` `)` escape が必要。

各フィルタは「危ない入力 (fence 文字 / 改行 / URL 特殊文字 / table 区切り 等) を入れても期待した escape が走る」ことをテストで担保する。

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
- `{% mood_view "template" with data %}` でサブテンプレートを呼ぶ場合は、`template_name` の拡張子から output_format を引き、対応する Environment で render する。

#### テンプレート著者の書き口

```jinja2
{# .md テンプレートでは md 用 Environment が使われる #}

{{ user_name }}                  {# md_escape が走る (ASCII punct backslash escape) #}
{{ user_code | inline_code }}    {# inline_code が Markup を返す → finalize は素通し #}
{{ raw_md_blob | safe }}         {# safe で Markup 化 → 素通し #}
```

#### 既存フィルタの移行

[generator.py](../../../../src/another_mood/components/generator/generator.py) で登録している既存フィルタも output_format モデルに揃える:

- `pluck`, `walk_entity` — 値取得系。Markup でなく素文字列を返す (= finalize で escape される)。フォーマット非依存。
- `to_yaml(flow=True)` — Markdown table cell 内に値をダンプする用途。fence 内の backtick 衝突問題 (「本仕様の対象外」節参照) を踏まえると、`table_cell` フィルタとの組み合わせ、もしくは `to_yaml` 自身を md フォーマット用のラッパーフィルタ扱いにすることを検討する。
- `mermaid_class_id` — Mermaid 識別子化。**Mermaid output_format 専用** のフィルタとして整理する (Mermaid テンプレート対応時)。

### 本仕様の対象外

以下は本仕様では扱わない。実際にニーズが顕在化した時点で別仕様として詰める:

- **Typed Value 機構** — 値が `mime_type` (例: `text/markdown`) と `content` を持つオブジェクトで、テンプレート側がスキーマに頼らず値自体を見て escape をバイパスする発想。汎用性は高いが、素 string 主体の入力形式では運用負荷が見合わない。
- **`md` 以外の output_format の具体仕様** — `html` / `adoc` / `sql` / `mermaid` の escape 関数とラッパーフィルタ。各 output_format を扱うテンプレートを実際に導入する段階で詰める。
- **入れ子 output_format** — FreeMarker の `XML{HTML}` のような「外側 XML / 内側 HTML で二重 escape」の表現。Markdown 内の Mermaid fence のような実需はあるが、単一フォーマットで動く基盤を確立した後に検討する。
- **ブロック単位の output_format 切替構文** — Twig の `{% autoescape 'js' %}` 相当。テンプレート内で部分的にフォーマットを切り替える独自タグ。入れ子 output_format と同じ理由で後送り。
- **anchor 系フィルタの escape** — [anchor-spec.md](anchor-spec.md) の percent-encoding 規則。アンカー実装と一緒に詰める。
- **`to_yaml(flow=True)` の fence 文字数調整** — 関連するが独立した個別事項。`inline_code` フィルタ整備で自然に吸収できる可能性がある。
