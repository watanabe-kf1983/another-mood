# Anchor Specification

データツリー上のノードの識別とリンク解決の仕様。ノードを一意に指す文字列を **アンカーパス** と呼ぶ。

## External Design

### 用語

- **ノード (node)**: データツリー上の一点 — レコード・クエリのグループ・シングルトン・ネストしたオブジェクト。リンクの宛先となる実体で、テンプレートでは `node()` で取得し `link` / `label` / `href` で整形する
- **アンカーパス (anchor path)**: そのノードを一意に識別する文字列（データツリー上の住所）。本ツールが生成する。URL fragment として URL に埋め込まれる
- **アンカー (anchor)**: HTML/Markdown の anchor target（`<a id="…">`）。リンクを受け止めるページ上の標識で、id にはアンカーパスを使う。mood_view が描画ノード（主題）に自動で刻むほか、`node | anchor` フィルタで手置きもできる（[リンク記法](#リンク記法) 参照）

> **背景: なぜリゾルバを `node()` と呼ぶか.** `link` / `label` / `href` は「ノードを受けて、そのノードの何かを描画する」フィルタ族で、アンカーターゲット (`<a id>`) を描画するフィルタの自然な名前は `data | anchor` — `<a id>` / `<a href>` の両面が `anchor` / `href` という対の名前で揃う。そこで anchor の語は HTML 本来の意味（受け側の標識）に予約し、リゾルバは「アンカーパスを解決して得られるもの」の名 — ノード — で `node()` とした。node / data tree は利用者向けリファレンス (`docs/reference/template.md` の Anchor paths 節) が先行して採用していた語彙でもある。

### ID 体系

アンカーパスは **データツリー上のパス** を `/` 区切りで表現した文字列。root を `/` とする **絶対パス形式**で、先頭の `/` が「データツリー root を起点とする絶対座標」であることを示す（相対参照と区別される）。

#### セグメント構成

データツリーを root から目的のノードまで辿り、各ステップを 1 セグメントとして書き出す:

- **dict キー（singleton 配下のキー）**: そのキーをそのまま使う
- **リスト要素**: その要素の `id` フィールドの値を使う

リスト要素に `id` フィールドが無い場合（Array pattern で id を schema 上要求していない場合、[schema-spec.md](../normalizer/schema-spec.md) 参照）、その要素はアンカーパスを持たない。到達経路を表現する手段がないため、配下のオブジェクトもアンカーパスを持たない。

#### Escape 規則

アンカーパスは **IRI**（RFC 3987）として扱う。URL fragment / パスとして使う以上 `/` を区切りに予約するため、**id 値が `/` を含む場合は percent-encoding (`%2F`) で escape する**（prose は例外、下記）。

それ以外の文字は **IRI エスケープ**で正規化する:

- **生のまま残す**: ASCII の unreserved (`A–Za–z0–9-._~`) と、**非 ASCII の `ucschar`**（RFC 3987 が IRI で許す Unicode 範囲。漢字・かな・非 ASCII 句読点・記号等。例: `書籍`、`モーニング娘。` の `。`、`藤岡弘、` の `、`）
- **percent-encode する**: ASCII の予約・特殊文字（空白 → `%20`、`# ? : * | \ " < >` 等）と、`ucschar` 外の非 ASCII（制御・format・surrogate・private-use・noncharacter）

つまりエスケープは「URI-encode から `ucschar` を除いた IRI 形」。アンカーパス（および由来する page_path）は **URL であると同時に出力ファイルのパス**でもあるため、IRI 形にすることで「人が読めるパス（`書籍.md`）」「URL として正当」「主要 OS で生成可能なファイル名」を同時に満たす。URI への直列化（`書籍`→`%E6%9B%B8%E7%B1%8D`）は消費側（Hugo の link render hook・ブラウザ・静的サーバ）が行う（URL の直列化自体は Hugo + 素の静的サーバで確認済み。リンクの着地に要る `<a id>` の描画は別問題で Hugo の raw HTML 許可を要する — Internal Design の「アンカーの raw HTML レンダリング」節を参照）。

エスケープは **encode 片道**で、生の segment/id 値に 1 回だけ適用する（既存の `%XX` を decode・二重 encode しない。`%` 自体は ASCII 特殊文字なので `%25` に encode される）。FS で危険な ASCII（`: * | \` 等）は上記のとおり encode 側に残るため Windows でも安全。

なお id value（データ側セグメント）は無制約だが、attr name（構造側セグメント）はスキーマの `^[\p{L}_][\p{L}\p{N}_]*$` で識別子状に制約済みで、ucschar/unreserved を素通りする。HTML5 の `id` 属性は空白を許容しないため、空白を含む id を持つレコードは技術的にアンカーパス化不可（[未決事項](#未決事項)参照）。

> **背景: なぜ IRI 形か.** エスケープは全非 ASCII を percent-encode せず、生 Unicode を残す **IRI 形**にする。anchor_path（および由来する page_path）はファイル名にもなり、`書籍`→`%E6…` では CJK プロジェクトで読めないファイル名になるため。「URL 安全 ≠ ファイル名安全」であり、IRI ⇄ URI は同一資源の別表現で、生 Unicode のリンク/ファイル名も CommonMark・HTML/URL 標準上正当なので生で残して問題ない。keep-raw 集合はカテゴリ（`\p{L}\p{N}`）でなく `ucschar`（レンジ）— `モーニング娘。`「藤岡弘、」のように **実在 id が非 ASCII 句読点を含む**ため。

`iri_escape` は文字単位の安全化までで、**文字単位で潰せない FS 固有問題**は別タスク [C7](node:/tasks/C/tasks/C7) で扱う — 事前の encode/validation で防ぐのではなく、`mkdir`/`open` の `OSError` を捕まえて**ユーザに改名を促す診断**を出す方針。対象:

- **パス長**（Windows `MAX_PATH`=260。anchor_path は階層を畳んだパスになるため、深いツリー + 長い id で**最も現実的に当たりやすい主リスク**）
- Windows 予約名（CON / NUL / COM1…）、末尾のドット・空白
- macOS の NFC/NFD 正規化、`ucschar` 内の Unicode 空白（U+3000 等）

`ucschar`（RFC 3987）のレンジ:

```
A0–D7FF, F900–FDCF, FDF0–FFEF,
10000–1FFFD, 20000–2FFFD, …, D0000–DFFFD, E1000–EFFFD
（サロゲート・noncharacter・private-use を除外）
```

#### Prose の例外

`prose` entity に限り、id 内の `/` を escape **せず** にアンカーパスへ素通しで埋め込む。

理由:

- `prose` の id は contents/ 内ファイルの相対パスから生成され、構造的にパス階層を持つ。これを `%2F` でエンコードすると `prose/design%2Farchitecture` のような可読性の低い文字列になる
- `prose` は flat な配列 entity で sub-entity を持たないため、resolver が `prose/` 以降を「単一の id」として扱えば曖昧性は発生しない

この例外は `prose` に固有のものとして明示的に定義する。一般化（「sub-entity を持たない配列 entity 一般に適用」等）はしない — 利用者 entity の構造変化に伴う将来の曖昧性混入を避けるため。

#### 例

正規化後の views データ:

```yaml
overview:                          # オブジェクト → singleton
  title: システム概要

erds:                              # 配列 → リスト
  - id: user-management
    title: ユーザー管理の ER図
    entities:                      # 配列 → リスト（ネスト）
      - id: user
        title: ユーザー
      - id: account
        title: アカウント
  - id: order-flow
    title: 受注フローの ER図
    entities:
      - id: user                   # 別の erd 配下なので user-management.entities.user とは別物
        title: ユーザー（注文視点）

screens:
  - id: user-list
    title: ユーザー一覧画面

prose:                             # flat list、id はファイル相対パス
  - id: design/architecture
    title: Architecture
  - id: design/normalizer/schema-spec
    title: Schema Specification
```

| アンカーパス | 指す対象 |
|---|---|
| `/` | root（views 全体） |
| `/overview` | overview singleton |
| `/erds/user-management` | user-management の ER図 |
| `/erds/user-management/entities/user` | user-management 配下の user エンティティ |
| `/erds/order-flow/entities/user` | order-flow 配下の user エンティティ（衝突しない） |
| `/screens/user-list` | user-list 画面 |
| `/prose/design/architecture` | Architecture 散文（id 内 `/` を素通し） |
| `/prose/design/normalizer/schema-spec` | Schema Specification 散文 |

旧仕様（`{class}.item.{id}` 形式）と異なり、新仕様ではアンカーパスが **データツリー上の到達経路そのもの** で構成されるため、ネストしたリスト要素間で id が重複してもアンカーパスが衝突しない。

#### クラスとの関係

class（[schema-spec.md](../normalizer/schema-spec.md) の Entity ID および ObjectType ID）は **型レベルの識別子** で、アンカーパスとは直交する概念:

- **class**: schema 上の位置を示す path-based 名（例: `categories.tasks`, `categories.item.tasks.item`）。クエリ DSL の `from:`、paging 設定、FK 解決、表示見出しで参照される
- **アンカーパス**: データツリー上の実体パス（例: `/categories/web/tasks/foo`）。リンク解決でのみ使われる

旧仕様ではアンカーパスを `{class}.{id}` と class 名込みで構築していたが、新仕様ではアンカーパスは実体パスのみで構成する。class はアンカーパス構築には登場しない。

### リンク記法

テンプレート内では **ノード** を `node()` で得て、整形フィルタで仕上げる:

```jinja2
{{ node("erds", erd.id, "entities", entity.id) | link }}
{# 位置引数 = 生セグメント（各 escape）→ ノード解決 → [<display>](<URL>) #}

{{ node(path="/erds/user-management/entities/user") | link }}
{# path= = 出来合いのアンカーパスを verbatim 解決（prose / 定数）#}

{{ member | link }}
{# すでに手にあるノードはそのまま整形できる #}

{{ node("erds", erd.id) | label }}   {# 表示文字列のみ #}
{{ node("erds", erd.id) | href }}    {# URL のみ #}
{{ member | link("ER 図") }}         {# display text を明示 override #}
{{ member | anchor }}                {# <a id="…"> 着地点を発行 #}
```

- `node(*segs, path=None)` — **ノード**を得る global 関数。引くアンカーパスを位置引数と `path=` の二部品から組み、**どちらが escape されるかが呼び出し側から見える**:
    - **位置引数 `segs`**: 生の値を各 **escape** し、`/seg` の形で後置する（最多の既定）。1 引数 = 1 セグメント（`/` 入りを 1 引数に混ぜない）。
    - **`path=`**: 出来合いのパス（prose id・定数・root `/`）を **verbatim** に前置する。
    - **併用**: `path=` を base に `segs` でその子を掘れる（`node("y", path="/prose/x")` → `/prose/x/y`）。片方だけでもよい。
    - **誤用は例外にしない**: 解決できないアンカーパスは MissingNode として可視化する（例: `/` 始まりの値を位置引数に渡すと `/%2F…` に escape され一致しない。[未解決参照の扱い](#未解決参照の扱い)）。
- `link` / `label` / `href` — ノード → Markdown リンク / 表示文字列 / URL。
- `anchor` — ノード → そのノードの着地点 `<a id="{anchor_path}">`。`href` が常時付ける fragment（[出力 URL の形式](#出力-url-の形式)）の受け側。id にはノード自身の anchor_path をそのまま使う（href の fragment と同一文字列なので両端が構築上一致する）。通常は mood_view が主題に自動で刻む（[mood_view 自動アンカー刻印](#mood_view-自動アンカー刻印)）ため、本フィルタは主題以外のノードに着地点を手置きするための原始機能。未解決参照（MissingNode）には何も発行しない（`href` が空を返すのと対称）。

アンカーパス**文字列**だけを返す公開フィルタは置かない。当初 `anchor_path(seg, *segs)` として公開していたが実需が一度も現れなかったため公開名から外した — 実需が出たら概念名と同じ `anchor_path` の名で再導入する（構築関数は内部に保持）。

display text は対象ノードから `title` → `name` → `id` → anchor_path 全体 のチェインで解決する。「末尾セグメント」を fallback に入れないのは、それが意味を持つのはリスト要素か入れ子オブジェクトに限られ、一般化できる fallback ではないため。`link(arg)` のように引数で渡せば override。

#### mood_view 自動アンカー刻印

一般のノードはページ上のどこに描かれるかをテンプレートしか知らないため、システムが着地点を任意に自動発行することはできない。ただし `{% mood_view %}`（およびルートテンプレート）は「この主題ノードを今ここに描く」ことを**システムが知っている唯一の経路**である。そこで描画はその主題のアンカーを出力の冒頭に自動で刻む（インラインはその場・分割/ルートはページ先頭）。これにより two-loop パターン（親が `| link`、子が分割/インライン）が、author の手置きなしに同ページ内 fragment 着地を成立させる。`| anchor` の手置きは、主題にせず本文で参照するだけのノード（テーブル行・リスト項目等）に着地点を与えるための escape hatch として残る。

実装は出力 format の post_process フックに置き、全レンダ経路が通る単一の漏斗（`TemplateEngine._render`）で主題が Node のとき刻む。フォーマット非依存の抽象スロットとし、`md` は `stamp_anchor` を束ねる。詳細は `output_formats/md.py` / `template_engine.py` の docstring。

#### 出力 URL の形式

出力する URL は **対象ページへの相対パス** + URL fragment。例: `[ユーザー](../erds/user-management.md#/erds/user-management/entities/user)`。

- **path 部**: source ページから target ページへの相対パス
- **fragment 部**: target ノードの anchor_path をそのまま使う (full anchor_path 形式)。常に付与する (target がページ root に一致する場合も省かない — ハンドリングを単純に保つ)。受け側の HTML id は `node | anchor` フィルタ（[リンク記法](#リンク記法)）が同じ文字列で `<a id>` を置く。fragment がページ内ジャンプとして機能するのは着地点が置かれた箇所のみ — mood_view が主題に自動で刻む（[mood_view 自動アンカー刻印](#mood_view-自動アンカー刻印)）か、author が `| anchor` で手置きした位置。ページ単位のリンクは path 部で機能する

#### 未解決参照の扱い

`node()` の組んだパスがマップに無いとき、解決失敗を `MissingNode`（試行パスを保持）として返す（例外は投げない）。整形側は壊れたリンクを「動くリンクの偽装」にせず、表示テキストを角括弧で囲んだ **`[text]` の形で可視化**する — `link` は表示テキストを `[..]` で囲んでリンク先を付けず、`href` は空文字列を返す。本文側の `relink` も同形に揃え、ソースの `[text](node:/missing)` からリンク先だけ落として `[text]` を残す（[prose body 処理フィルタ `relink`](#prose-body-処理フィルタ-relink)）。

> **背景: 素テキストでなく角括弧を残す.** リンクを外して素テキストにすると解決成功時の通常テキストと見分けがつかず、失敗が出力に埋もれる。`[text]` は対応する参照定義を持たない shortcut reference として CommonMark が角括弧ごとそのまま描画するため、壊れた参照が目立つ。表示テキストは常に残るので author は気づいて直せる。当初は `link` を素テキスト・`relink` を `[text]` と割っていたが、両者を `[text]` に統一した。

### Markdown 本文中のアンカー参照

> テンプレート側のリンク解決・整形フィルタは [リンク記法](#リンク記法) を参照。

prose body 等の Markdown 本文では、リンク先に `node:` スキーム + アンカーパスを書いてノードを参照する。**インラインリンク形のみ**を対象とする:

```markdown
ユーザーの詳細は[ユーザー](node:/erds/user-management/entities/user)を参照。
```

この記法は二役を兼ねる:

1. **author 向け sugar** — author がノードを明示的に参照したいときの書き方。テンプレートの `node(path="/…") | link`（[リンク記法](#リンク記法)）の本文版で、解決後は同じ `[display](URL)` になる
2. **canonical intermediate form** — Normalizer がソース相対リンクから変換した先の中間表現

ソース Markdown では普通の相対パスで書け、Normalizer が `node:` 記法に変換する ([markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照):

```markdown
{# ソース: {contents_dir}/design/normalizer/normalizer.md #}
[Composer](../composer/composer.md)
↓ Normalizer が変換 ↓
[Composer](node:/prose/design/composer/composer)
```

#### 対象はインラインリンク形のみ

`[text](node:…)` のインライン形だけを解決する。参照形（`[text][label]` + 別行 `[label]: node:…`）と autolink（`<node:…>`）は **恒久的に非対応**（後回しの deferral でなく非ゴール）。理由:

- A5 が生成するのはインライン形のみ。参照・autolink が出るのは手書きの場合だけで、実利用上の頻度はきわめて小さい（インライン ≫ 参照 > autolink）
- autolink は素だと表示テキストが URL になり、参照形は未解決時の plain 化が「リンク位置」と「定義行」に跨って綺麗に畳めない — どちらも対応コストに対し需要が薄い
- 利用者には「手書きの `node:` 参照はインライン形で書く」と案内すれば足りる

#### scheme 名を `node:` とする背景

リンク先の実体をテンプレートでは `node()` で解決する。本文側の scheme も同じ語に揃え、`[x](node:/…)` ↔ `node(path="/…") | link` を一目で対応づけられるようにする。`anchor` は受け側（`<a id>`）に予約済みなので scheme には使わない。`node:` は実在 URI スキームと衝突しない。アンカーパス参照以外の内部 URL を将来挟む場合は、傘名前空間（`mood:` 等）でなく種類ごとに別 scheme を立てる方針。

### prose body 処理フィルタ `relink`

prose body 中の `node:` リンク先を、表示先ページからの相対 URL（[出力 URL の形式](#出力-url-の形式)）に置換する pre-render フィルタ。**リンク解決の単一責務**に絞る — 見出し深さ調整は別フィルタ `under_heading`（`docs/reference/template.md` の under_heading）と合成する:

```jinja2
{{ prose.body.content | relink | under_heading("##") }}
```

author の明示適用を最低線とする（schema が prose body 型を宣言していればアクセス時に自動処理する暗黙適用は別タスク）。

未解決の `node:` 参照（マップに無いアンカーパス）は、`link` フィルタの MissingNode 契約（[未解決参照の扱い](#未解決参照の扱い)）に倣い、**表示テキストを角括弧で囲んでリンク先を外す**（`[text](node:/missing)` → `[text]`）。死んだ `node:` リンクとして出力して「動くリンクの偽装」にしない。ビルドレポートへの警告は `link` 側と揃えて [B10](node:/tasks/B/tasks/B10) で後日扱う。実装機構は [generator.md の prose body 処理フィルタ](generator.md#prose-body-処理フィルタ) を正本とする。

## Internal Design

### リンク解決

リンク解決の内部配線（フィルタの 2 群構成・供給経路・レポートルート相対の座標系・page_path / URL をノードに焼かない判断）はこの文書では持たず、[generator.md のリンク解決](generator.md#リンク解決) と [ページパスの導出](generator.md#ページパスの導出) を正本とする。実装レベルの契約（`link` / `href` / `relink` に `@pass_context` が要る理由、`anchor` には不要なこと、`MissingNode` を整形フィルタ側で捌き `node_href` には渡さないこと）は `generator/data_tree_filters.py` と `generator/output_formats/md.py` の docstring に残している。

### アンカー (`<a id>`) の raw HTML レンダリング (Hugo unsafe)

`node | anchor` と mood_view 自動刻印が出す着地点は **raw HTML** の `<a id="…">`。Hugo の Goldmark は既定（`markup.goldmark.renderer.unsafe = false`）で raw HTML を `<!-- raw HTML omitted -->` に潰すため、bundled `resources/hugo/hugo.toml` で **`unsafe = true`** を設定している。これが無いと fragment の着地点が描画されず、リンクはページには着くがノード位置までジャンプしない。

> **背景: unsafe=true のトラストモデル.** Another Mood は **著者が所有するデータベース** をレンダーする SSG で、Hugo 既定の `unsafe=false`（untrusted な Markdown をレンダーするモデル向けの防御）とは前提が異なる。raw HTML を通しても露出は狭い: データ値 `{{ field }}` は md 出力 format の finalize で `md_escape` され（`<`→`\<`）無害化され、code span / fenced block の内容は Goldmark が `unsafe` と無関係に常に HTML エスケープする。新たに通る raw HTML は **著者自身のテンプレート・prose・(verbatim 外の) `| safe`** のみで、著者は既にソースとテンプレートの全権を持つため escalation にはならない。Hugo/Jekyll/MkDocs 等も自前コンテンツには unsafe HTML を許可するのが標準。

## Proposals

### 見出しノード (A3, A4)

> **未実装** — [markdown-parser-spec.md の見出し抽出](../normalizer/markdown-parser-spec.md#見出し抽出-a1)（タスク [A1, A3〜A5, A7](node:/tasks/A/tasks/A1)）で導入。本節は anchor 側の住所付けとリンク解決への波及を定める。

prose 本文中の見出しを **node（リンクの宛先）** として扱う。データツリー上は prose レコード配下の `headings` リスト要素なので、既存の「ネストしたリスト要素 = node」規則にそのまま乗る。見出しは別レコードではなく、prose レコード内の住所（着地点）だけを持つ。

#### アンカーパス: `/prose/X#slug`

見出しノードの anchor_path は **`<prose レコードの anchor_path>#<github-slug>`**（例 `/prose/design/normalizer/architecture#エラー処理`）。

- `#` は **構造的セパレータ**で、`/` と同様に raw で挿入し `url_escape` に通さない。slug は github 互換で `#` を含まず、prose id はファイルパスで `#` は `%23` に escape される。したがって anchor_path 中のリテラル `#` は **見出し区切りの一個だけ** で、`rsplit("#", 1)` が常にページ部と見出し slug に割れる
- 中間の `headings` セグメントは畳む（`/prose/X/headings/slug` でなく `/prose/X#slug`）。[anchor_path 構築](#id-体系) で、[Prose の例外](#prose-の例外)（`safe="/"` 分岐）の隣にもう一つ分岐を置き、見出しノードは親 prose レコードの anchor_path に `#` + slug を繋ぐ

resolver は無変更 — anchor_path 文字列をキーにした辞書引き（`build_node_map`）のまま、見出しノードもそのキーで解決される。

#### Prose の例外への追補

[Prose の例外](#prose-の例外) は「prose は sub-entity を持たない」を前提に `prose/` 以降を単一 id として扱うが、見出し導入で prose は派生 sub-entity（`headings`）を持つ。不変条件は **`#` が境界** であることで保たれる: `prose/<id>` から `#` の手前までが単一 id（従来どおり）、`#` 以降がページ内見出し。`/`-曖昧性は生じない。

#### 出力 URL の fragment 規則の一般化

[出力 URL の形式](#出力-url-の形式) の「fragment = target ノードの anchor_path 全体」を次に一般化する:

> **fragment = anchor_path の最後の `#` 以降。`#` が無ければ anchor_path 全体。**

- データノード `/prose/X` → fragment `/prose/X`（全体。mood_view が刻む `<a id="/prose/X">` に着地）
- 見出しノード `/prose/X#エラー処理` → fragment `エラー処理`（`#` 以降。Goldmark/GitHub が見出しに打つ native id `<h2 id="エラー処理">` に着地）

#### 見出しは stamp しない（native id 着地）

データノードのアンカー（`<a id="{anchor_path}">`）は mood_view / `| anchor` が **刻む** — 合成 id はどのレンダラも自動生成しないため。見出しの id は逆に **Goldmark/GitHub が native で打つ** ので刻まない（自前で刻むと native id と重複 id になる）。住み分け: **合成 id（ノード）は刻む／自然 id（見出し）は renderer 任せ**。したがって見出しノードは [mood_view 自動アンカー刻印](#mood_view-自動アンカー刻印) や `| anchor` の対象外。

#### node: 本文参照の fragment

[Markdown 本文中のアンカー参照](#markdown-本文中のアンカー参照) の `node:` 記法は、見出しを URI の fragment で運ぶ:

```markdown
[エラー処理](node:/prose/design/normalizer/architecture#エラー処理)
```

path 部がページ（prose ノード）を、`#エラー処理` がページ内見出しを指す。`relink` はページをノード解決し、上記 fragment 規則で `#エラー処理` を出力 URL に乗せる。これは A7（見出し fragment 対応）がソース相対リンク `[t](architecture.md#エラー処理)` から生成する中間形でもある（[markdown-parser-spec.md の見出し fragment 対応](../normalizer/markdown-parser-spec.md#見出し-fragment-対応-a7)）。見出しが対象 prose に無ければ MissingNode として可視化（[未解決参照の扱い](#未解決参照の扱い)）。

#### テンプレートからの見出しリンク（`node(fragment=)`）

テンプレートが見出しノードを引くときは、[リンク記法](#リンク記法) の `node` に `fragment=` を加える（B11 で入った `path=` の上に A 群で乗せる三つめの kwarg）:

```jinja2
{{ node(path="/prose/design/normalizer/architecture", fragment="エラー処理") | link }}
```

`path` に `#` + slug を **raw** で連結して anchor_path を組む（`fragment` は `url_escape` しない — slug は github 互換で `#` を含まず、`#` は構造的セパレータ）。現行シグネチャ `node(*segs, path=None)` に `fragment=None` を足し、`resolve_node`（`data_tree_filters.py`）が組む anchor 文字列の末尾（`path` 前置 + `segs` 後置の後ろ）に `#` + fragment を繋ぐよう拡張すればよい。`fragment` 単独など解決できない組み合わせは、他と同じく MissingNode として可視化される（例外にしない）。見出しノードが `node_map` に載ってから実装・テストできる。

### 未決事項

- **空白を含む id の扱い**: HTML5 の `id` 属性は空白不可のため、空白を含む id はアンカーパス化不可。ビルド時に警告して当該 id 配下をアンカーパス無し扱いとする方針（[F4 / D 群と連携、未タスク化](node:/tasks/F/tasks/F4a)）
