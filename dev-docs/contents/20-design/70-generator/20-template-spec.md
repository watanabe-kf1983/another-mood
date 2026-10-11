# Template Specification

## External Design

### テンプレート主題のノード受け取りと `this` 束縛

> **[W4 dup]** ↔ template_engine.py:137-145 _bind、render_processor.py:51-53 (a)、template.md:139-165,116 (b)、10-generator:41 (c) — 完全。案: 残す (設計判断 3 点が主)。docs/コードの再掲部分は縮める

主題（subject）を `this` でどう参照するか（Mapping の spread／`this`／Array 反復、スカラ値の扱い）は `docs/reference/template.md` の Subtemplate side を正本とする。設計判断:

- **束縛はレンダリング境界（`template_engine._bind`）の単一規則**として root テンプレート（`index.md`）と `render` フィルタのサブテンプレートに同一適用する。利用者から見えるデータモデルがツリー全体で一致し、root も自ノードを `this` で参照できる。`render` フィルタ側はパス決定とノードのパススルーだけを担い、context 構築を持たない。
- 主題が `this` でノードとして取れることはリンク解決の足場でもある — source ページ（主題ノード）を `this` から得られるので、resolver は per-render の source-node 束縛を持たず静的な `(PagingPolicy, node_map)` だけを束縛すればよい（[anchor-spec.md のリンク解決](30-anchor-spec.md#リンク解決)）。
- 分割するのはノード主題だけで、スカラ主題は `file_per` に関わらず常に inline 展開するのは、ページはアンカーパスを持つノードであるべきだから（inline 展開は単なる差し込みなので任意の値を許す）。

### 分割ルール

> **[W4 dup]** ↔ template.md:112-137,262-276 (b)、render_processor.py:39-45,78-81、heading_shift.py:1-18 (a) — 部分。案: 残す (決定 2 つ)。見出し深さの段落は docs にある→縮める

`render` フィルタが主題の `_meta.object_type_id` を `file_per` と照合して分割/インラインを決めること、親ページのリンクは render が自動生成せず author が `| link` で書く two-loop パターン（分割なら別ページ URL・インラインなら同ページ `#fragment` に自動適応）は `docs/reference/template.md` の Split vs inline を正本とする。設計判断:

> **決定: 親リンクを render に畳み込まない.** リンク解決は既に `| link` ＋ page_path が持ち分割/インラインへ自動適応するので、render に持たせると二重実装になり、親側の周辺マークアップ（リスト記号等）も author の制御外になる。render の責務は「このノードの内容をどこに置くか」に保つ。

> **決定: インラインは型単位ポリシー（call-site 上書きは持たない）.** インライン意図は型を `file_per` から外して表現する。file_per 対象の型を call-site で `inline` 強制すると、そのノードが自前ページとインライン本文に**二重出力**され、`| link` の指す先と実体の所在がずれる（footgun）。

> **見出し深さ.** subtemplate が「見出し＋本文」を一単位で再利用したいとき、埋め込み先によって見出しレベルが変わる（同じ型を `##` 下でも `###` 下でも置きたい）。この深さ調整は render 固有ではなく、生成側の `under_heading` フィルタ（任意の埋め込み出力をブロックで囲む／prose body をパイプで処理）が担う。split 時に render が `""` を返す性質と合わさり、同じ記述が分割でもインラインでも正しく出る。仕様は `docs/reference/template.md` の `under_heading` を参照。

### 描画の単一ページ不変条件 (render subtree ガード)

> **[W4 dup]** ↔ render_processor.py:94-139 _guard_subtree docstring (a, ほぼ逐語)、template.md:110 (b)、80-showcase:173、40-paging:59 (c) — 完全。不変条件+理由。案?: 不変条件と「構造判定で edition 非依存」の理由は design が正本→残し、docstring を縮める。機構 (identity 判定、免除の条件) は削除→コード

[リンク解決](30-anchor-spec.md#リンク解決)は次の不変条件に乗っている: **各ノードは *データ位置* で一意に定まる 1 ページ (`PagingPolicy.page_path`) にだけ描かれる**。source は `page_path(this)`、target は `page_path(target)` — 両者が同じ規則でノードのデータ位置からページを引くからこそ、`| link` / `href` / `relink` が一貫して相対化できる。`render` フィルタで `this` の subtree 外にノードを inline 描画するとこの不変条件が破れ、`page_path(subject)` が実描画ページと食い違って、そのノードの内部 `this` 起点リンクも、そのノードへ張る被リンクも壊れる。

そこで render フィルタは、subject が `this` の子孫（subject から `_parent` を遡上して `this` に identity 一致）でなければ、描画元テンプレートのファイル付き（行は無い）のビルドエラーにする。判定は **構造（子孫）** で行い、split / inline や edition (file_per) に依存しない — 妥当性をテンプレート単体で決めたいため（同じ呼び出しが「split する edition では通り、しない edition では弾かれる」ような edition 依存エラーを避ける）。

**非ノード subject は免除**（anchor も page identity も持たない）。ただしこの免除が健全なのは、その子テンプレが `this` 起点の描画（`link` / `href` / `anchor` / `relink`・アンカー刻印）を一切しないときに限る。id 等を受け取り内部でノードを引き直して描く子テンプレはガードの射程外で、リンク正当性は author 責任になる（例: meta の `record_table.md` は entity id を受けてデータ行の表を描くのみで、entity ノード自体は配置しない）。他所のノードを描きたいときはクエリ (join 等) で subtree に取り込んで子孫化するか、`| link` で参照する。導出規則とコードは `render_processor.py` の `_guard_subtree` docstring が正本。

### 背景: なぜ undefined アクセスをエラーにしないか

> **[W4 dup]** ↔ template_engine.py:69-71 (a)、template.md:378-389 (b) — 部分。案: 決定 (chainable) はコード、3 段階比較と切替条件は appendix

> **[W4 → appendix?]** 推奨: 移す

minijinja は `undefined_behavior` で undefined アクセスの扱いを選べる: 厳密な `strict`（全ての undefined アクセスでエラー）、チェイン可能な `chainable`、既定の `lenient`（1 階層目はサイレント、`{{ x.a }}` のチェインはエラー）の 3 段階を提供する。

本プロジェクトは `chainable` を明示指定する（既定のままでは `{{ x.a }}` がエラーになる）。理由:

- 内蔵テンプレート・ユーザテンプレートのいずれも、スキーマから抽出される optional フィールド（`metadata`, `validation` 等）を頻繁に参照するため、ガードの記述負荷が重い
- `lenient` は 1 階層目の typo も同様にサイレント失敗するため、チェインだけエラーにする中途半端な挙動になっている
- 厳密な typo 検出が必要になった時点で `strict` への切り替えを検討する（その際は内蔵テンプレート側のガード追加が必要）

なお `chainable` でも minijinja 組込みフィルタは undefined を受けない（`{{ x | length }}` は raise。jinja2 の `ChainableUndefined` は `0` を返した）。次節の「何も描かない」規則が及ぶのは本ツールのヘルパー。

### 欠損値は何も描かない

> **[W4 dup]** ↔ md.py:164-206、data_tree_filters.py:90-93,120-122 (a)、20-anchor-spec:165 (c)、template.md (b) — 完全。案?: 規約の宣言 (不変条件) は残す。missing と欠損の区別・link の text の挙動は削除→docs/コード

欠損した値をテンプレートが描こうとしたとき、出力は空になる。フィルタや関数を通した場合も同じで、ヘルパーが `"None"` のような表現を発明することはない。この規則があるので [10-json-data-model.md](../40-communication/10-json-data-model.md#配列内オブジェクトのフィールド統一) の「nullable な項目は値ではなくフィールドごと省略する」規約が成り立つ。

**欠損と「壊れた参照」は別に扱う。** 解決を試みて外した参照（missing node）は、リンクに描く `link` / `relink` では目立つ `[text]` を出す（`href` は空、`anchor` は何も出さない）。一方 optional フィールドの欠損は上の規約が認めている正常系なので、目立たせず何も描かない。`node` / `child` の住所を組み立てる引数が欠損したときは、参照そのものが成立しないので missing node にもならず、何も描かれない。

**`link` の表示テキスト。** 引数を渡さなければ label、渡した値が欠損していれば空のテキスト（`[](url)`）になる。参照は健在なので、表示テキストの欠損でリンクごと消すことはしない。

### テンプレートの語彙は filter / test / operator に限る

> **[W4 dup]** ↔ template_engine.py:77-83 コメント (理由まで同内容) (a)、template.md:391-399 (b) — 完全。案?: 設計判断は design が正本→残し、template_engine.py のコメントを一文に縮める

値そのものはメソッドを持たない。minijinja の `pycompat` は Python の文字列 / list / dict メソッドを値に生やすが、これを切っている（`.startswith()` は空描画ではなくメソッド名つきのエラー）。

理由は **利用者に案内できる境界が引けること**。pycompat を入れたままだと「どこまでが Python 相当か」を答える主体が居ない — 本ツールの `docs/` には書けず（Python のどの版のどのメソッドか特定できない）、minijinja コアの保証でもない（実体は minijinja-contrib の `unknown_method_callback` で、上流の位置づけも「Jinja2 テンプレートの移行互換シム」。COMPATIBILITY.md も *Filters should generally be used instead of methods* と述べる）。語彙を filter / test / operator に閉じれば、案内できる集合とテンプレートから届く集合が一致する。

### 出力フォーマット

テンプレートエンジンの出力フォーマット (Markdown / HTML / Mermaid 等) ごとに escape 関数と位置依存ヘルパを切り替える仕組みの仕様。

利用者向けの API 仕様 (`md_escape` の振る舞い・位置依存ヘルパの使い方) は `docs/reference/template.md` を参照。本仕様は設計判断と内部構造に絞る。

#### 課題

> **[W4 → appendix?]** 推奨: 移す

テンプレートエンジンに出力フォーマット別の escape 機構が無いと、ユーザ入力に出力フォーマットの特殊文字 (Markdown なら `*` `_` `|` `` ` `` `<` 等) が混じった瞬間に出力が壊れる。Jinja2 標準の `autoescape` は HTML escape 決め打ちで、Markdown / Mermaid / AsciiDoc / SQL 等の非 HTML フォーマットに直接は使えない。

複数フォーマットを並行サポートしつつ、フォーマット別の escape をテンプレート著者の書き忘れに頼らず保証できる機構が要る。

#### Escape 方針: ASCII punctuation 一律 backslash escape

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

#### 位置依存ヘルパの 2 分類

> **[W4 dup]** ↔ template.md:455-466 (b)、md.py:50-73 (a) — 部分。案: 残す

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

#### ユーザ提供 Python ヘルパは受け付けない

> **[W4 dup]** ↔ 25-template-trust-model:9-15,49-54 (c, 部分)。案: 残す (具体的な却下対象はここのみ)

`<projectDir>/filters.py` の auto-load や entry points 経由でsbdb プロジェクト固有の Python ヘルパを登録する仕組みは **意図的にサポートしない**。

ソース（sbdb プロジェクト）を書いた人とそのソースでツールを動かす人が一致するとは限らない。任意 Python の実行を許すと、配布されたsbdb プロジェクトを `mood build` した時点で第三者の手元で任意コードが走る。これは Excel マクロウィルスと同型の問題で、被害は受け取り側に発生する。この「著者 ≠ 実行者」の信頼境界と、テンプレート実行そのものの扱いは [template-trust-model.md](25-template-trust-model.md) に一般化して整理している。

整形ニーズは Jinja2 標準フィルタ + 本仕様の位置依存ヘルパ + [meta-template filters](#outputformat-と-meta-template-filters-の住み分け) (built-in メタ用、ユーザ非公開) で吸収する。これらで足りないケースが顕在化したら、Python 任意実行を経由しない手段 (宣言的 DSL の拡張、データ側での事前整形 等) で詰める。

## Internal Design

### 欠損の描画責務と「引数未指定」の区別

> **[W4 dup]** ↔ omitted.py:12-20、data_tree_filters.py:90-93 (誤リンク例まで同文)、template_engine.py:112-124 as_template_helper、md.py 各ヘルパ、meta_templates.py (a) — 完全。案?: 「None は欠損、OMITTED は未指定」の不変条件と 3 分類は design→残し、omitted.py/resolve_node の docstring を縮める。各ヘルパの個別挙動は削除→コード

`None` は「値が欠損している」の意味に予約する。「引数が渡されていない」には番兵 `OMITTED`（`omitted.py`）を使う。既定値を `None` にすると 2 つが区別できず、最も重い失敗は `node(path=…)` で起きる — `path` の欠損で prefix が空になり、`node("y", path=欠損)` が `/y` に解決して**別の実在ノードへ静かにリンクする**。表示の劣化ではなく誤リンク。

欠損を描くのは `_finalize` 一点で、ヘルパーは欠損を文字列化せず `None` を返す。テキストを被写体に取るものは境界（`as_template_helper`）が包むので、欠損はプロセッサに届かない。

引数の欠損は結果ごと消さず、その引数が担う仕事だけを失わせる。引数が何をするかで 3 通りに分かれる:

- **表示に混ざるだけ**（`link` の `text`）→ その箇所が空になる
- **出力の形を選ぶ**（`code_fenced` の `language`、`to_yaml` の `flow`）→「渡されていない」と同じ扱い
- **住所を組み立てる**（`node` の `segs` / `path` / `fragment`、`child` の `seg`）→ 参照が成立しないので `None`。ここだけ「空にする」が使えない（上の誤リンクになる）

番兵を入れるのは、この 3 通りのうち「渡されていない」と挙動が分かれるものだけ。例外は 2 つあり、`under_heading` の `marker` は既定値が無く、囲みの深さが決まらないと描けないので raise のまま（欠損を静かに扱わない唯一の場所）。コレクションを返す `walk_entity` は空コレクションを返す（`{% if rows %}` / `for` が回る形を保つ）。

#### 背景: 外した 2 案

> **[W4 → appendix]**

**フィルタ入口で `None` を「空文字で描かれる番兵」へ変換する。** jinja2 の配置をそのまま再現でき、フィルタは無改造で済む。外した理由は、(a) 意図的に渡された `null` と欠損を区別できない、(b) 全フィルタ呼び出しに引数走査の層が乗る、(c) フィルタが `None` を返す形は迂回ではなく素直な意味論であり、番兵という間接層を挟む必要がない。

**`link` の `text` が欠損したら label へフォールバックする。** リンクが使える形で残るのは利点だが、著者が `t.別名` と書いたのに黙って `名前` を出すのは、フィルタに暗黙の `default()` を埋め込むこと。フォールバックが要る著者には `t.別名 or t.名前` / `| default(...)` という明示手段があり、*explicit is better than implicit* に反する。データ欠損が出力から検出できなくなる点も悪い（空なら表セルが空くので気づける）。

### finalize-based escape の選択

> **[W4 dup]** ↔ template_engine.py:53-60,73-76 make_environment コメント (理由まで) (a, 完全)。注意: 「コードを読んでも理由は復元できない」は古い。案?: 設計判断→design に残し、コードのコメントを縮める。逆 (コード正本、ここは削除) も可

エンジンの auto-escape は HTML escape 決め打ちで、escape 関数の差し替え口が無い（minijinja はテンプレート名の拡張子で有効化を決める）。output_format ごとに escape を切り替えるため、auto-escape を `auto_escape_callback` で無条件に切り、`finalizer` フックで `output_format.escape(str(value))` を適用する方式を採る。

> **[W4 fix]** 不整合: この一文は古い。template_engine.py make_environment のコメント (53-60, 73-76) に理由が既にある

コードを読んで `finalizer=_finalize` を見ても理由は復元できないため、保守時に「auto-escape に戻したい」誘惑に乗らないようここに残す。

### Markup 返却契約

> **[W4 dup]** ↔ md.py 各ヘルパコメント、render_processor.py:73-75 (a, 部分)。案: 残す (不変条件の一般化はここのみ)

`finalize` は `Markup` を素通しする。ヘルパは **`Markup` を返したら、そのヘルパが内部のあらゆる escape を完了させていなければならない**。契約違反のヘルパはセーフネットを素通って崩れた出力を出す。

新しい位置依存ヘルパを追加する際の不変条件。各ヘルパの具体的な実装責務 (CommonMark 6.1 制約、padding 規則、safe-set 等) は `md.py` のコメントと `test_md.py` で担保する。

### OutputFormat と meta-template filters の住み分け

> **[W4 dup]** ↔ meta_templates.py:4,126-135、md.py:263-264 (a, 部分)。案: 残す

`md.py` のモジュール定数 `MD_GLOBALS` / `MD_FILTERS` は **「出力フォーマット固有の位置依存正規化」** のためだけに使う。built-in メタテンプレートが必要とする補助関数 (カタログデータへの dotted-key access、parent_entity 連鎖 descent、YAML ダンプ、ノードのアンカーパス取り出し) はフォーマット非依存・位置非依存でメタテンプレート専用のドメインヘルパなので、`meta_templates.py` に `META_TEMPLATES_FILTERS` として持ち、メタ edition の `extra_filters` としてのみ注入する。

新しい補助関数を追加する際の判定:

- フォーマット固有 (位置依存正規化) → `MD_GLOBALS` / `MD_FILTERS`
- メタテンプレート固有 (カタログ走査・整形) → META_TEMPLATES_FILTERS

境界を曖昧にしてフォーマット側にメタ専用 filter を混ぜると、将来 output_format を追加するたびに同じ filter を再登録する DRY 違反になり、メタテンプレートの依存をユーザテンプレートにも漏らしてしまう。

### ヘルパの配線とフォーマットの注入

> **[W4 dup]** ↔ template_engine.py:31-33,62-64 OutputFormat docstring、generator.py:186-225 (a, 完全)。案?: 構造の一文 (注入、エンジンはヘルパを登録しない) は残す。docstring と重なる説明は削除

`OutputFormat` が持つのは render policy（escape 関数・ブロック空白制御・`post_process`）だけで、ヘルパは policy ではない。フォーマットの静的ヘルパ (`MD_GLOBALS` / `MD_FILTERS`) も、paging と node map に束縛されるリンクフィルタ (`make_link_filters(paging, node_map)`、[anchor-spec.md#リンク解決](30-anchor-spec.md#リンク解決)) も、合成点である Generator が edition ごとに組み立てて `TemplateEngine` の `filters` / `globals` に渡す。エンジン自身はヘルパを一つも登録しない。

`make_environment` / `TemplateEngine` は使う `OutputFormat` を **注入で受け取る**（具象フォーマットを import しない）。汎用エンジンが具象フォーマットを名指しすると `template_engine → md` の循環依存になるため、フォーマットの選択は合成点 (Generator) に寄せる。

### render サブテンプレートの output_format 解決

`subject | render("template.md")` でサブテンプレートを呼ぶ場合、`template_name` の拡張子から output_format を引き、対応する Environment で render する想定。テンプレート参照に拡張子が含まれていること（利用者向け仕様は `docs/reference/template.md` の render）に依存する。

現状は MD output_format に決め打ち。複数 output_format を扱うテンプレートが登場した時に実装する制約として記録しておく。

## Proposals

以下は本仕様では扱わない。実際にニーズが顕在化した時点で別仕様として詰める:

- **CommonMark の他の位置依存正規化** — indented code block、link title、autolink 等。実需が顕在化したら既存ヘルパと同じ枠組みで追加する
- **Prose 型に的を絞った mime_type 多態** — text/markdown 以外の prose (text/html をページとして解釈する等) を、レコード直下の `mime_type` を分岐キーに扱う機構。かつて「Typed Value 機構」(値が `mime_type` と `content` を持ち、テンプレートがスキーマに頼らず値自体を見て振る舞いを変える汎用の発想) として検討したが、一般機構としては採らない — ユーザデータに厳密な型を宣言させることがこのツールのアイデンティティであり、スキーマ非依存の値検査はそれと矛盾する。多態を要求しうるのは組み込みコレクション (prose / blob) に限られ、型はレコード直下の `mime_type` (envelope のヘッダ相当、[blob-spec.md](../50-normalizer/27-blob-spec.md#レコード形状の判断) 参照) が持つ。機構はその布石の上に、実需が顕在化した時点で Prose 型特化として詰める
- **`md` 以外の output_format の具体仕様** — `html` / `adoc` / `sql` / `mermaid` の escape 関数とラッパーフィルタ。各 output_format を扱うテンプレートを実際に導入する段階で詰める
- **入れ子 output_format** — FreeMarker の `XML{HTML}` のような「外側 XML / 内側 HTML で二重 escape」の表現。Markdown 内の Mermaid fence のような実需はあるが、単一フォーマットで動く基盤を確立した後に検討する
- **ブロック単位の output_format 切替構文** — Twig の `{% autoescape 'js' %}` 相当。テンプレート内で部分的にフォーマットを切り替える独自タグ。入れ子 output_format と同じ理由で後送り
