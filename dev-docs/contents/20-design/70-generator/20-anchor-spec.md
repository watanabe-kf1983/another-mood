# Anchor Specification

データツリー上のノードの識別とリンク解決の仕様。ノードを一意に指す文字列を **アンカーパス** と呼ぶ。

## External Design

### 用語

- **ノード (node)**: データツリー上の一点 — レコード・クエリのグループ・シングルトン・ネストしたオブジェクト。リンクの宛先となる実体で、テンプレートでは `node()` で取得し `link` / `label` / `href` で整形する
- **アンカーパス (anchor path)**: そのノードを一意に識別する文字列（データツリー上の住所）。本ツールが生成する。URL fragment として URL に埋め込まれる
- **アンカー (anchor)**: HTML/Markdown の anchor target（`<a id="…">`）。リンクを受け止めるページ上の標識で、id にはアンカーパスを使う。mood_view が描画ノード（主題）に自動で刻むほか、`node | anchor` フィルタで手置きもできる（[アンカーの発行](#アンカーの発行) 参照）

> **背景: なぜリゾルバを `node()` と呼ぶか.** `link` / `label` / `href` は「ノードを受けて、そのノードの何かを描画する」フィルタ族で、アンカーターゲット (`<a id>`) を描画するフィルタの自然な名前は `data | anchor` — `<a id>` / `<a href>` の両面が `anchor` / `href` という対の名前で揃う。そこで anchor の語は HTML 本来の意味（受け側の標識）に予約し、リゾルバは「アンカーパスを解決して得られるもの」の名 — ノード — で `node()` とした。node / data tree は利用者向けリファレンス (`docs/reference/template.md` の Anchor paths 節) が先行して採用していた語彙でもある。

### ID 体系

アンカーパスは **データツリー上のパス** を `/` 区切りで表現した文字列。root を `/` とする **絶対パス形式**で、先頭の `/` が「データツリー root を起点とする絶対座標」であることを示す（相対参照と区別される）。

#### セグメント構成

データツリーを root から目的のノードまで辿り、各ステップを 1 セグメントとして書き出す:

- **dict キー（singleton 配下のキー）**: そのキーをそのまま使う
- **リスト要素**: その要素の `id` フィールドの値を使う

リスト要素に `id` フィールドが無い場合（Array pattern で id を schema 上要求していない場合、[schema-spec.md](../50-normalizer/20-schema-spec.md) 参照）、その要素はアンカーパスを持たない。到達経路を表現する手段がないため、配下のオブジェクトもアンカーパスを持たない。

#### Escape 規則

アンカーパスは **IRI**（RFC 3987）として扱う。URL fragment / パスとして使う以上 `/` を区切りに予約するため、**id 値が `/` を含む場合は percent-encoding (`%2F`) で escape する**（prose は例外、下記）。

それ以外の文字は **IRI エスケープ**で正規化する:

- **生のまま残す**: ASCII の unreserved (`A–Za–z0–9-._~`) と、**非 ASCII の `ucschar`**（RFC 3987 が IRI で許す Unicode 範囲。漢字・かな・非 ASCII 句読点・記号等。例: `書籍`、`モーニング娘。` の `。`、`藤岡弘、` の `、`）
- **percent-encode する**: ASCII の予約・特殊文字（空白 → `%20`、`# ? : * | \ " < >` 等）と、`ucschar` 外の非 ASCII（制御・format・surrogate・private-use・noncharacter）

つまりエスケープは「URI-encode から `ucschar` を除いた IRI 形」。アンカーパス（および由来する page_path）は **URL であると同時に出力ファイルのパス**でもあるため、IRI 形にすることで「人が読めるパス（`書籍.md`）」「URL として正当」「主要 OS で生成可能なファイル名」を同時に満たす。URI への直列化（`書籍`→`%E6%9B%B8%E7%B1%8D`）は消費側（Hugo の link render hook・ブラウザ・静的サーバ）が行う（リンクの着地に要る `<a id>` の描画は別問題で Hugo の raw HTML 許可を要する — Internal Design の「アンカーの raw HTML レンダリング」節を参照）。

エスケープは **encode 片道**で、生の segment/id 値に 1 回だけ適用する（既存の `%XX` を decode・二重 encode しない。`%` 自体は ASCII 特殊文字なので `%25` に encode される）。FS で危険な ASCII（`: * | \` 等）は上記のとおり encode 側に残るため Windows でも安全。

なお id value（データ側セグメント）は無制約だが、attr name（構造側セグメント）はスキーマの `^[\p{L}_][\p{L}\p{N}_]*$` で識別子状に制約済みで、ucschar/unreserved を素通りする。HTML5 の `id` 属性は空白を許容しないため、空白を含む id を持つレコードは技術的にアンカーパス化不可（[未決事項](#未決事項)参照）。

> **背景: なぜ IRI 形か.** エスケープは全非 ASCII を percent-encode せず、生 Unicode を残す **IRI 形**にする。anchor_path（および由来する page_path）はファイル名にもなり、`書籍`→`%E6…` では CJK プロジェクトで読めないファイル名になるため。「URL 安全 ≠ ファイル名安全」であり、IRI ⇄ URI は同一資源の別表現で、生 Unicode のリンク/ファイル名も CommonMark・HTML/URL 標準上正当なので生で残して問題ない。keep-raw 集合はカテゴリ（`\p{L}\p{N}`）でなく `ucschar`（レンジ）— `モーニング娘。`「藤岡弘、」のように **実在 id が非 ASCII 句読点を含む**ため。

escape 規則は文字単位の安全化までで、**文字単位で潰せない FS 固有問題**は別タスク [C7](node:/tasks/C/tasks/C7) で扱う — 事前の encode/validation で防ぐのではなく、`mkdir`/`open` の `OSError` を捕まえて**ユーザに改名を促す診断**を出す方針。対象:

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

`prose` entity に限り、アンカーパスの構成に二つの例外を置く。

**id 内の `/` は素通し** — escape せずにアンカーパスへそのまま埋め込む。理由:

- `prose` の id は contents/ 内ファイルの相対パスから生成され、構造的にパス階層を持つ。これを `%2F` でエンコードすると `prose/design%2Farchitecture` のような可読性の低い文字列になる
- `prose` は flat な配列 entity で sub-entity を持たないため、resolver が `prose/` 以降を「単一の id」として扱えば曖昧性は発生しない

この例外は `prose` に固有のものとして明示的に定義する。一般化（「sub-entity を持たない配列 entity 一般に適用」等）はしない — 利用者 entity の構造変化に伴う将来の曖昧性混入を避けるため。

**見出しは `#slug` に畳む** — prose 本文中の見出しは node（リンクの宛先）として扱う。データツリー上は prose レコード配下の `headings` リスト要素（[markdown-parser-spec.md の見出し抽出](../50-normalizer/30-markdown-parser-spec.md#見出し抽出)）で「ネストしたリスト要素 = node」規則に乗るが、anchor_path では中間の `headings` セグメントを畳み、**`<prose レコードの anchor_path>#<github-slug>`** とする（`/prose/X/headings/slug` でなく `/prose/X#slug`、例 `/prose/design/normalizer/architecture#エラー処理`）。見出しは別レコードではなく、prose レコード内の住所（着地点）だけを持つ。

`#` は `/` と同様に raw で挿入する構造的セパレータ。slug は github 互換で `#` を含まず、id 内の `#` は `%23` に escape されるため、anchor_path 中のリテラル `#` は見出し区切りの一個だけ。「`prose/` 以降は単一 id」の前提も、`#` の手前までを単一 id と読み替えることでそのまま保たれ、`/`-曖昧性は生じない。

> **既知の穴**: 二例外の検知はどちらもデータツリー位置ベースで、クエリの `join:` / `flatten:` を経て別位置に現れた prose には発火しない。位置独立化は [prose 検知の位置独立化 (B13)](#prose-検知の位置独立化-b13) で扱う。

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
    headings:                      # 本文見出し（markdown-parser-spec.md の見出し抽出）
      - { id: エラー処理, title: エラー処理, level: 2 }
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
| `/prose/design/architecture#エラー処理` | Architecture 本文中の見出し（`headings` セグメントは畳む） |
| `/prose/design/normalizer/schema-spec` | Schema Specification 散文 |

アンカーパスは **データツリー上の到達経路そのもの** で構成されるため、ネストしたリスト要素間で id が重複してもアンカーパスは衝突しない。

#### クラスとの関係

class（[schema-spec.md](../50-normalizer/20-schema-spec.md) の Entity ID および ObjectType ID）は **型レベルの識別子** で、アンカーパスとは直交する概念:

- **class**: schema 上の位置を示す path-based 名（例: `categories.tasks`, `categories.item.tasks.item`）。クエリ DSL の `from:`、paging 設定、FK 解決、表示見出しで参照される
- **アンカーパス**: データツリー上の実体パス（例: `/categories/web/tasks/foo`）。リンク解決でのみ使われる

class はアンカーパスの構築には登場しない。

### リンクの解決と着地

解決されたリンクがどう URL になり、ページ上のどこに落ちるかの規則。テンプレートの `node()`（[リンク記法](#リンク記法)）から来ても本文の `node:`（[Markdown 本文中のアンカー参照](#markdown-本文中のアンカー参照)）から来ても共通で、送り側（URL の fragment）と受け側（ページ上の id）が同じ文字列 — データノードは anchor_path、見出しノードは slug — を使うことで両端が構築上一致する。

#### 出力 URL の形式

出力する URL は **対象ページへの相対パス** + URL fragment。例: `[ユーザー](../erds/user-management.md#/erds/user-management/entities/user)`。

- **path 部**: source ページから target ページへの相対パス
- **fragment 部**: **anchor_path の最後の `#` 以降。`#` が無ければ anchor_path 全体**。常に付与する (target がページ root に一致する場合も省かない — ハンドリングを単純に保つ)
    - データノード `/prose/X` → fragment `/prose/X`（全体）。[アンカーの発行](#アンカーの発行)の規則で置かれた `<a id>` に着地する。fragment がページ内ジャンプとして機能するのは着地点が置かれた箇所のみで、ページ単位のリンクは path 部で機能する
    - 見出しノード `/prose/X#エラー処理` → fragment `エラー処理`（`#` 以降）。Goldmark/GitHub が見出しに打つ native id（`<h2 id="エラー処理">`）に着地する（[Prose の例外](#prose-の例外)）

#### アンカーの発行

一般のノードはページ上のどこに描かれるかをテンプレートしか知らないため、システムが着地点を任意に自動発行することはできない。ただし `{% mood_view %}`（およびルートテンプレート）は「この主題ノードを今ここに描く」ことを**システムが知っている唯一の経路**である。そこで描画はその主題のアンカー（`<a id="{anchor_path}">`）を出力の冒頭に自動で刻む（インラインはその場・分割/ルートはページ先頭）。これにより two-loop パターン（親が `| link`、子が分割/インライン）が、author の手置きなしに同ページ内 fragment 着地を成立させる。`| anchor`（[リンク記法](#リンク記法)）の手置きは、主題にせず本文で参照するだけのノード（テーブル行・リスト項目等）に着地点を与えるための escape hatch として残る。

**見出しノードには発行しない**。見出しの id は Goldmark/GitHub が native で打つので、システムが刻むと native id と重複 id になる。住み分けは **合成 id（ノード）は刻む／自然 id（見出し）は renderer 任せ** — 自動刻印・`| anchor` とも見出しには何も発行しない（[Prose の例外](#prose-の例外)）。

#### 未解決参照の扱い

`node()` の組んだパスがマップに無いとき、解決失敗を `MissingNode`（試行パスを保持）として返す（例外は投げない）。整形側は壊れたリンクを「動くリンクの偽装」にせず、表示テキストを角括弧で囲んだ **`[text]` の形で可視化**する — `link` は表示テキストを `[..]` で囲んでリンク先を付けず、`href` は空文字列を返し、`anchor` は何も発行しない。本文側の `relink` も同形に揃え、ソースの `[text](node:/missing)` からリンク先だけ落として `[text]` を残す（[prose body 処理フィルタ `relink`](#prose-body-処理フィルタ-relink)）。

> **背景: 素テキストでなく角括弧を残す.** リンクを外して素テキストにすると解決成功時の通常テキストと見分けがつかず、失敗が出力に埋もれる。`[text]` は対応する参照定義を持たない shortcut reference として CommonMark が角括弧ごとそのまま描画するため、壊れた参照が目立つ。表示テキストは常に残るので author は気づいて直せる。当初は `link` を素テキスト・`relink` を `[text]` と割っていたが、両者を `[text]` に統一した。

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

{{ node(path="/prose/design/architecture", fragment="エラー処理") | link }}
{# fragment= = ページ内見出しの slug（見出しノード）#}
```

- `node(*segs, path=None, fragment=None)` — **ノード**を得る global 関数。引くアンカーパスを位置引数・`path=`・`fragment=` の三部品から組み、**どれが escape されるかが呼び出し側から見える**:
    - **位置引数 `segs`**: 生の値を各 **escape** し、`/seg` の形で後置する（最多の既定）。1 引数 = 1 セグメント（`/` 入りを 1 引数に混ぜない）。
    - **`path=`**: 出来合いのパス（prose id・定数・root `/`）を **verbatim** に前置する。
    - **`fragment=`**: 見出し slug を `#{fragment}` として **raw** で末尾に付ける（escape しない — slug は github 互換で `#` を含まず、`#` は構造的セパレータ。[Prose の例外](#prose-の例外)）。
    - **併用**: `path=` を base に `segs` でその子を掘れ（`node("y", path="/prose/x")` → `/prose/x/y`）、`fragment=` は最後に乗る。片方だけでもよい。
    - **誤用は例外にしない**: 解決できないアンカーパスは MissingNode として可視化する（例: `/` 始まりの値を位置引数に渡すと `/%2F…` に escape され一致しない。`fragment` 単独も同様。[未解決参照の扱い](#未解決参照の扱い)）。
- `link` / `label` / `href` — ノード → Markdown リンク / 表示文字列 / URL。
- `anchor` — ノード → そのノードの着地点 `<a id="{anchor_path}">`。通常は自動刻印が主題に刻むため、本フィルタは主題以外のノードに着地点を手置きするための原始機能（発行の規則と例外は[アンカーの発行](#アンカーの発行)）。

アンカーパス**文字列**だけを返す公開フィルタは置かない。当初 `anchor_path(seg, *segs)` として公開していたが実需が一度も現れなかったため公開名から外した — 実需が出たら概念名と同じ `anchor_path` の名で再導入する（構築関数は内部に保持）。

display text は対象ノードから `title` → `name` → `id` → anchor_path 全体 のチェインで解決する。「末尾セグメント」を fallback に入れないのは、それが意味を持つのはリスト要素か入れ子オブジェクトに限られ、一般化できる fallback ではないため。`link(arg)` のように引数で渡せば override。

### Markdown 本文中のアンカー参照

> テンプレート側のリンク解決・整形フィルタは [リンク記法](#リンク記法) を参照。

prose body 等の Markdown 本文では、リンク先に `node:` スキーム + アンカーパスを書いてノードを参照する。**インラインリンク形のみ**を対象とする:

```markdown
ユーザーの詳細は[ユーザー](node:/erds/user-management/entities/user)を参照。
```

この記法は二役を兼ねる:

1. **author 向け sugar** — author がノードを明示的に参照したいときの書き方。テンプレートの `node(path="/…") | link`（[リンク記法](#リンク記法)）の本文版で、解決後は同じ `[display](URL)` になる
2. **canonical intermediate form** — Normalizer がソース相対リンクから変換した先の中間表現

ソース Markdown では普通の相対パスで書け、Normalizer が `node:` 記法に変換する ([markdown-parser-spec.md](../50-normalizer/30-markdown-parser-spec.md) 参照):

```markdown
{# ソース: {contents_dir}/design/normalizer/normalizer.md #}
[Composer](../composer/composer.md)
↓ Normalizer が変換 ↓
[Composer](node:/prose/design/composer/composer)
```

#### 見出しへの fragment 参照

`node:` 記法は見出しを URI の fragment で運ぶ:

```markdown
[エラー処理](node:/prose/design/normalizer/architecture#エラー処理)
```

path 部がページ（prose ノード）を、`#エラー処理` がページ内見出しを指す（[Prose の例外](#prose-の例外)）。`relink` はこの文字列全体を見出しノードとして解決し、[出力 URL の形式](#出力-url-の形式)の fragment 規則で `#エラー処理` を出力 URL に乗せる。見出しが対象 prose に無ければ MissingNode として可視化する（[未解決参照の扱い](#未解決参照の扱い)）。

ソース相対リンク `[t](architecture.md#エラー処理)` の `#fragment` は、Normalizer が `node:` 変換時に透過で運んでこの形を生成する（[markdown-parser-spec.md のリンク正規化](../50-normalizer/30-markdown-parser-spec.md#リンク正規化)）。

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

未解決の `node:` 参照は MissingNode 契約（[未解決参照の扱い](#未解決参照の扱い)）どおり `[text]` に畳む。ビルドレポートへの警告は `link` 側と揃えて [B10](node:/tasks/B/tasks/B10) で後日扱う。実装機構は [generator.md の prose body 処理フィルタ](10-generator.md#prose-body-処理フィルタ) を正本とする。

## Internal Design

### リンク解決

リンク解決の内部配線（フィルタの 2 群構成・供給経路・レポートルート相対の座標系・page_path / URL をノードに焼かない判断）はこの文書では持たず、[generator.md のリンク解決](10-generator.md#リンク解決) と [ページパスの導出](10-generator.md#ページパスの導出) を正本とする。実装レベルの契約（`link` / `href` / `relink` に `@pass_context` が要る理由、`anchor` には不要なこと、`MissingNode` を整形フィルタ側で捌き `node_href` には渡さないこと）は `generator/data_tree_filters.py` と `generator/output_formats/md.py` の docstring に残している。[出力 URL の形式](#出力-url-の形式)の fragment 規則と stamp 可否は、anchor_path 文字列の再パースでなく見出し検知述語から導出するノード属性で持つ（`generator/data_tree.py` の `_NodeMeta` docstring）。

### アンカー自動刻印の実装

自動刻印（[アンカーの発行](#アンカーの発行)）は出力 format の post_process フックに置き、全レンダ経路が通る単一の漏斗（`TemplateEngine._render`）で主題が Node のとき刻む。フォーマット非依存の抽象スロットとし、`md` は `stamp_anchor` を束ねる。詳細は `output_formats/md.py` / `template_engine.py` の docstring。

### アンカー (`<a id>`) の raw HTML レンダリング (Hugo unsafe)

`node | anchor` と mood_view 自動刻印が出す着地点は **raw HTML** の `<a id="…">`。Hugo の Goldmark は既定（`markup.goldmark.renderer.unsafe = false`）で raw HTML を `<!-- raw HTML omitted -->` に潰すため、bundled `resources/hugo/hugo.toml` で **`unsafe = true`** を設定している。これが無いと fragment の着地点が描画されず、リンクはページには着くがノード位置までジャンプしない。

> **背景: unsafe=true のトラストモデル.** Another Mood は **著者が所有するデータベース** をレンダーする SSG で、Hugo 既定の `unsafe=false`（untrusted な Markdown をレンダーするモデル向けの防御）とは前提が異なる。raw HTML を通しても露出は狭い: データ値 `{{ field }}` は md 出力 format の finalize で `md_escape` され（`<`→`\<`）無害化され、code span / fenced block の内容は Goldmark が `unsafe` と無関係に常に HTML エスケープする。新たに通る raw HTML は **著者自身のテンプレート・prose・(verbatim 外の) `| safe`** のみで、著者は既にソースとテンプレートの全権を持つため escalation にはならない。Hugo/Jekyll/MkDocs 等も自前コンテンツには unsafe HTML を許可するのが標準。

## Proposals

### prose 検知の位置独立化 (B13)

> **一部実装** — 由来フィールド `origin_item_type` の catalog への導入・刻印・参照伝搬まで実装済み。位置独立な prose 検知（generator 述語の由来ベースへの差し替え）と、行再構築 stage の明示 carry は未了。Phase 13 タスク [B13](node:/tasks/B/tasks/B13)。

[Prose の例外](#prose-の例外)の二例外（`/`-素通しと見出しの fold）は、どちらも「このノードは prose か」の検知をデータツリー位置（`object_type_id == "prose.item"` 等）で行う。しかし prose はクエリの `join:` / `flatten:` で任意の位置に現れるため、位置ベースの検知はそこで発火しない。

実例が showcase/music にある: `album_tracklist` クエリは prose を `liner` として singleton-flatten し、album ページに `{% mood_view "prose.md" with liner %}` でインライン描画する。この liner ノードの位置は `album_tracklist.item.liner` であり、`prose.item` を見る検知は素通りする。liner 本文中の見出しは、それ自体は album ページに native id で着地するのに fold は発火せず、generic 形（`/album_tracklist/X/liner/headings/slug`）の anchor_path が生成され、[fragment 規則](#出力-url-の形式)でも slug に割れないため見出しリンクが壊れる。showcase/music の `liner` は実際に `# Liner notes` 見出しを持ち、`background.md` が view 経由でこの見出しへリンクしている — 現状この参照は generic な anchor_path のため壊れており（bare `[…]`）、generator 述語を由来ベースに差し替えると解決する。

検知の根拠を位置から **型の由来（provenance）** に移す: catalog が「この型の row はどの entity のレコードに由来するか」を保持し、generator は `object_type_id → 由来 ObjectType id` の対応で prose を同定する。

#### 背景: 固有述語（duck-typing）案の不採用

レコードの形状（`body.mime_type == "text/markdown"`）で prose を見分ける案は検討のうえ不採用とした:

- [Prose の例外](#prose-の例外)の設計原則「一般化（構造で適用範囲を決めること）はしない — 利用者 entity の構造変化に伴う曖昧性混入を避けるため」と正面衝突する。判定基準を「位置」から「形」に替えただけの構造ベース判定であり、利用者が markdown body を持つ entity を作った瞬間、その id の `/` が無 escape で素通りし曖昧性が silent に混入する
- `select:` が `headings` を残して `body` を落とすと fold の検知が消える（catalog 由来なら射影に影響されない）
- 形状判定が由来判定より広く効く唯一の位置は singleton-flatten の wrapper（後述）だが、そこは `/`-例外が不要な位置なので追加カバレッジにならない

#### 機構: `origin_item_type` フィールド

`Node`（tree 形）に `origin_item_type: str | None`、`ObjectType`（flat 形）に `origin_item_type: str` を追加する。値は由来 entity の ObjectType id（例 `prose.item`）。**tree は識別子確定前なので `None` を許すが、flat 型は必ず identity を持つため由来は常に解決済みで `None` にならない** — 未刻印のノードは flatten 時に「自身を由来とする」へ解決する（`_to_object_type` が `node.origin_item_type or 自身の item_type id`）。

> **背景: 由来を flat で materialize し、lookup 側フォールバックにしない.** 当初案は「値には実由来だけを持たせ、`未刻印=自身` は generator の lookup 時に補う」だった。しかし flat 型は必ず id を持つのに「id はあるが由来が `None`」は非対称で、`str | None` を露出すると全 consumer に None 分岐が漏れる。flatten の一箇所で self へ解決（materialize）すれば由来は総関数（常に `str`）になり、消費側は分岐不要、解決規則も単一箇所に集まる。代償は `__definition.entities` に self 由来が冗長に載ることだが、`__entity_defs` には出ないため実害は小さい（下記 ClassVar）。

- **名前**: `origin_item_type`。「source」は本コードベースで多義（`From` の source / `user_source/` / `Diagnostic.source`）なので避け、`Attribute.child_item_type` と対称な `..._item_type` を採る
- metadata に相乗りさせない: metadata は schema 著者情報（title / description）の入れ物で `__entity_defs` が verbatim 描画するため、由来を載せると system key が露出する。専用フィールドなら露出はテンプレート側の opt-in に留められる（下記 ClassVar）
- `Attribute`（`child_item_type` の隣）でもない: 由来は型に内在する性質で、Attribute / Edge は「親から見た辺」。クエリの row 型（`album_tracklist.item` 等）は Entity 直下で親 attribute を持たないため、Attribute 側に row 由来の置き場がない

処理の流れ:

- **stamp**: `data_catalog._build_entity_node`（flat→tree 変換）で、各 source entity に自身の ObjectType id を**無条件**で刻む。`build_tree` は source catalog に対し一度だけ走り（view は query derive が参照で再配線し `build_tree` へ再入しない）、保存すべき前段 stamp が無いため上書きガードは要らない
- **伝搬**: derive は `Node` を参照で再配線するため大半は自動（`From` / `Merge` の right / `Select` の子 / `Flatten` の inline 子 / `Grouped` の subtree）。参照経由の子が由来を保持することは、join / grouped の派生で `…tasks.item` が `tasks.item` を保つとして実証済み
- **行再構築 stage の明示 carry（未了）**: `Select` / `Merge` / `Flatten` は row ノードを metadata ごと落として再構築するため参照 carry が効かず、現状は self に解決する。`from: prose` + `select:` で row の prose-ness を保つには由来を明示 carry する必要がある
- **合成ノードは自身が由来**: `Grouped` の group row と `Flatten` で dissolve された wrapper は新規の合成型で、どの entity のレコードでもない。`Node` 側は無印（`None`）で始まり flatten で自身の id に解決する。規則: **row を保つ変換（where / sort / select / join / flatten）は由来を保持し、合成ノードは自身を由来とする**
- **serde**: `ObjectType.origin_item_type` は materialize 済みで常に永続化に現れる。`from_dict` は dict に無ければ自身の id へ default（手書き dict 用の robustness で、materialize 済み本番データでは発火しない）。`Node` 側の `None` は従来どおり elide
- **ClassVar**: `Entity.catalog` に `item_type.origin_item_type` エッジを足す（dataclass フィールドと ClassVar 自己記述の完全一致を保つ）。それでも `__entity_defs` に由来は出ない — `entity_def.md` は item_type の id / metadata / attributes のみ明示描画し由来を参照せず、メタ entity（`__definition.entities`）の def ページ自体が非公開だから。由来をメタドキュメントへ能動表示するのは F4c
- **generator**: composer が data-catalog を sources にマージ済みなので、`__definition.entities` から `{item_type.id: origin_item_type}` の辞書を組める（値は materialize 済みで常に存在）。ObjectType が無い位置（配列 `…item[]` 等）だけ position id にフォールバックし、両述語とも偽になる
- **判定の差し替え（未了）**: `/`-例外 = 由来が `prose.item`、見出し fold = 由来が `prose.item.headings.item`

運搬路は実証済み: content-schema の `title: Prose headings` が派生 entity `album_tracklist.item.liner.headings.item` の metadata に既に写っており、`origin_item_type` も同じ経路（`Node` の参照渡し + `flatten_tree` の書き写し）に載る。

#### 背景: ObjectType の無い位置は identity フォールバックで安全に倒せる

由来判定は「ノードの位置 (`object_type_id`) → catalog の ObjectType → `origin_item_type`」という辞書引きなので、位置に対応する ObjectType が catalog に無いノードでは由来が引けず、position id へのフォールバックで両述語とも偽に倒れる。この取りこぼしが prose 検知の新たな穴にならないことを確認しておく。

catalog は singleton オブジェクトを独自の ObjectType にせず、dotted 属性として親 row に inline する（`liner.id` / `liner.body.mime_type` の形式）。prose レコードが singleton になるのは `flatten:`（singleton 化）の `as:` 位置だけで、それ以外の現れ方 — トップレベルのパススルー、`join:` でのリスト添付、`grouped:` 配下、`select:` を通した行 — では prose レコードは配列要素のままであり、`Node` が参照で生存して ObjectType が catalog に生成されるため、判定に穴は無い。

残る singleton-flatten 位置（`album_tracklist.item.liner` 等）では:

- **`/`-例外はそもそも不要**: この例外が効くのは prose の id 値（`/` を含みうる）がアンカーパスの segment になる場面、つまり prose レコードが**配列要素**である場面に限る。singleton 位置のノードの segment は dict キー（`liner`）であり、prose id は segment に現れない
- **見出し fold は判定できる**: `headings` 配下は dotted inline の先で `Node` が参照生存し、`album_tracklist.item.liner.headings.item` の ObjectType が catalog に生成される（現に生成されている）ため、`origin_item_type` を運べる

つまり辞書引きが取りこぼす唯一の位置は、`/`-例外が構造的に不要で、fold は子ノード側で判定できる位置と一致する。

#### 未決事項 (B13)

- **由来の粒度は型でありフィールドではない**: `select: {item: title, as: id}` のように id を挿げ替える射影では型の由来が `prose.item` のまま残り、`/`-例外が title 値に適用されうる（実害は `/` を含む値のみ）。フィールド単位の由来追跡はスコープ外として記録
- **メタドキュメンテーションへの能動表示**: 由来は ClassVar に載るがテンプレートは描画しない。`__entity_defs` / per-query ER 図（[F4c](node:/tasks/F/tasks/F4c)）に由来をラベル表示する改善は任意の後続

### 未決事項

- **空白を含む id の扱い**: HTML5 の `id` 属性は空白不可のため、空白を含む id はアンカーパス化不可。ビルド時に警告して当該 id 配下をアンカーパス無し扱いとする方針（[F4 / D 群と連携、未タスク化](node:/tasks/F/tasks/F4a)）
