# Anchor Specification

アンカー（リンク可能なオブジェクト）の識別とリンク解決の仕様。アンカーを一意に指す文字列を **アンカーパス** と呼ぶ。

## Proposals

> **未実装** — Phase 11 タスク [B4, B5](../../../tasks.md)（anchor フィルタ群 / prose body `resolve` フィルタ）。親参照注入 (B1)・`_meta.anchor_path` / `_meta.object_type_id` 注入 (B3)・anchor_path → ノードマップ (B2)・page_path 導出 (B6) は実装済み — [generator.md](generator.md#%E3%83%8E%E3%83%BC%E3%83%89%E3%83%A1%E3%82%BF%E3%83%87%E3%83%BC%E3%82%BF) 参照。

### 用語

- **アンカー (anchor)**: リンクされ得る位置・対象。HTML/Markdown の anchor target と同義。本ツールではデータツリー上の各ノードがアンカーとなる
- **アンカーパス (anchor path)**: そのアンカーを一意に識別する文字列。本ツールが生成する。URL fragment として URL に埋め込まれる

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

つまりエスケープは「URI-encode から `ucschar` を除いた IRI 形」。アンカーパス（および由来する page_path）は **URL であると同時に出力ファイルのパス**でもあるため、IRI 形にすることで「人が読めるパス（`書籍.md`）」「URL として正当」「主要 OS で生成可能なファイル名」を同時に満たす。URI への直列化（`書籍`→`%E6%9B%B8%E7%B1%8D`）は消費側（Hugo の link render hook・ブラウザ・静的サーバ）が行う（Hugo + 素の静的サーバで end-to-end 確認済み）。

エスケープは **encode 片道**で、生の segment/id 値に 1 回だけ適用する（既存の `%XX` を decode・二重 encode しない。`%` 自体は ASCII 特殊文字なので `%25` に encode される）。FS で危険な ASCII（`: * | \` 等）は上記のとおり encode 側に残るため Windows でも安全。

なお id value（データ側セグメント）は無制約だが、attr name（構造側セグメント）はスキーマの `^[\p{L}_][\p{L}\p{N}_]*$` で識別子状に制約済みで、ucschar/unreserved を素通りする。HTML5 の `id` 属性は空白を許容しないため、空白を含む id を持つレコードは技術的にアンカーパス化不可（[未決事項](#未決事項)参照）。

> **背景: なぜ IRI 形か.** エスケープは全非 ASCII を percent-encode せず、生 Unicode を残す **IRI 形**にする。anchor_path（および由来する page_path）はファイル名にもなり、`書籍`→`%E6…` では CJK プロジェクトで読めないファイル名になるため。「URL 安全 ≠ ファイル名安全」であり、IRI ⇄ URI は同一資源の別表現で、生 Unicode のリンク/ファイル名も CommonMark・HTML/URL 標準上正当なので生で残して問題ない。keep-raw 集合はカテゴリ（`\p{L}\p{N}`）でなく `ucschar`（レンジ）— `モーニング娘。`「藤岡弘、」のように **実在 id が非 ASCII 句読点を含む**ため。

`iri_escape` は文字単位の安全化までで、**文字単位で潰せない FS 固有問題**は別タスク [C7](../../../tasks.md) で扱う — 事前の encode/validation で防ぐのではなく、`mkdir`/`open` の `OSError` を捕まえて**ユーザに改名を促す診断**を出す方針。対象:

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

#### テンプレート内のアンカー参照

テンプレート内では **アンカー** を `anchor()` で得て、整形フィルタで仕上げる:

```jinja2
{{ anchor("erds", erd.id, "entities", entity.id) | link }}
{# segments からアンカーを組み立て解決 → [<display>](<URL>) の Markdown リンク #}

{{ anchor("/erds/user-management/entities/user") | link }}
{# 第一引数が `/` 始まり → 出来合いのアンカーパスとして解決（prose / 定数）#}

{{ member | link }}
{# すでに手にあるノード（＝アンカー）はそのまま整形できる #}

{{ anchor("erds", erd.id) | label }}   {# 表示文字列のみ #}
{{ anchor("erds", erd.id) | href }}    {# URL のみ #}
{{ member | link("ER 図") }}           {# display text を明示 override #}
```

- `anchor(seg, *segs)` — segments（各セグメントを escape）か、`/` 始まりの出来合いアンカーパスから、**アンカー**（リンク可能なオブジェクト）を得る。関数形・フィルタ形（`"/..." | anchor`）の両用。第一引数の `/` 始まりで raw 判定するのは安全 — エンティティ/クエリ名は識別子パターン（`/` 始まり不可、schema-schema / query-schema の `propertyNames`）に縛られるため。1 引数 = 1 セグメント（`/` 入りを 1 引数に混ぜない）。
- `link` / `label` / `href` — アンカー → Markdown リンク / 表示文字列 / URL。
- `anchor_path(seg, *segs)` — 解決せずアンカーパス**文字列**のみ欲しいとき（fragment や `toc:` 組み立て等）。入力規則は `anchor` と同じ。

display text は対象アンカーから `title` → `name` → `id` → anchor_path 全体 のチェインで解決する。「末尾セグメント」を fallback に入れないのは、それが意味を持つのはリスト要素か入れ子オブジェクトに限られ、一般化できる fallback ではないため。`link(arg)` のように引数で渡せば override。

#### Markdown 本文中のアンカー参照

prose body 等の Markdown 本文では `toc:` プレフィックス記法でアンカーパスを URL として埋め込む:

```markdown
ユーザーの詳細は[ユーザー](toc:/erds/user-management/entities/user)を参照。
```

この記法は二役を兼ねる:

1. **author 向け sugar** — author が anchor で明示的に参照したいときの書き方
2. **canonical intermediate form** — Normalizer がソース相対リンクから変換した先の中間表現

ソース Markdown では普通の相対パスで書け、Normalizer が `toc:` 記法に変換する ([markdown-parser-spec.md](../normalizer/markdown-parser-spec.md) 参照):

```markdown
{# ソース: {contents_dir}/design/normalizer/normalizer.md #}
[Composer](../composer/composer.md)
↓ Normalizer が変換 ↓
[Composer](toc:/prose/design/composer/composer)
```

### リンク解決

リンク解決は Generator の **pre-render 段階で完結**する。post-render での文字列置換は行わない。

- **`anchor()` + `link` / `label` / `href` フィルタ**: `anchor()` でアンカーを得て、`link` / `label` / `href` が Markdown リンク / display text / URL を生成
- **prose body 処理フィルタ (仮称 `resolve`)**: prose body 中の `toc:` URL を実 URL に置換。anchor 解決以外にも見出しレベル正規化やエスケープ調整等を兼ねる総合処理フィルタ

出力する URL は **対象ページへの相対パス** + URL fragment。例: `[ユーザー](../erds/user-management.md#/erds/user-management/entities/user)`。

URL は **path 部 + fragment 部** に分けて組み立てる:

- **path 部**: source ページから target ページへの相対パス
- **fragment 部**: target ノードの `_meta.anchor_path` をそのまま使う (full anchor_path 形式)。HTML id 側も同じ文字列で発行する ([generator.md](generator.md) の id 発行と対応)。常に付与する (target がページ root に一致する場合も省かない — ハンドリングを単純に保つ)

resolver とフィルタは **レポートルート相対 座標系**で動く (page_path の定義に同じ — [generator.md](generator.md#ページパスの導出-b6) 参照。`reports/`・profile 段は付かない)。ページパスは `config.page_path(node)` ([B6](../../../tasks.md)) で算出する。page_path はノードに焼かず、resolver が必要時に config から引く:

- **source ページパス**: テンプレートコンテキストの `this`（主題ノード）から `config.page_path(this)`。`@pass_context` フィルタが context 経由で取る
- **target ページパス**: anchor_path → ノードマップで target ノードを引いて `config.page_path(target_node)`
- **path 部の算出**: フィルタが `posixpath.relpath(target_page_path, source ページのディレクトリ)` で計算（page_path は `/` 区切りなので `posixpath` で OS 非依存に保つ）。source/target が同一レポート内なら共通のマウント先 (`reports/[{profile}/]`) は相殺されるので、原点をレポートルートに取って差し支えない
- **最終 URL**: `{path 部}#{target._meta.anchor_path}`

ノードには page_path も結合済み URL も焼かない。fragment は常に anchor_path から派生し、page_path は config 依存なので、いずれも URL を必要とするフィルタ側でその場で組む。

path を組む `link` / `href` は `@pass_context` で受ける必要がある。理由は二つ — (1) source node を context の `this`（主題ノード）から取るため、(2) Jinja2 オプティマイザの定数畳み込みを抑止するため（定数引数の `{{ anchor("/erds/x") | href }}` がコンパイル時に評価されると相対 URL がキャッシュに焼かれ、同テンプレートを別ページから使ったとき壊れる）。source 非依存の `label` / `anchor` は `@pass_context` 不要。

フィルタは依存方向で 2 群に分かれる:

- **フォーマット非依存の中立フィルタ** (`anchor` / `anchor_path` / `label`): anchor マップだけに束縛され、ノード・パス文字列・表示テキストを返す。出力フォーマットも render context も要らない。`anchor.make_anchor_filters(anchor_map)` が供給する
- **フォーマット固有の整形フィルタ** (`link` / `href`): 出力フォーマットが所有し `ReportsConfig` に束縛されて Markdown リンク / URL を組む。source node は焼かず `@pass_context` が `this` から取る。`md.make_link_filters(config)` が供給し、`OutputFormat.link_filters` 経由でフォーマットに属する（Environment 構築時に config で配線。フォーマットが自分のフィルタ面全体を所有する — [output-format-spec.md](output-format-spec.md) 参照）

`anchor` がアンカーパス → アンカーを引き、整形フィルタが URL を組み立てる。

**未解決参照の扱い**: `anchor()` の組んだパスがマップに無いとき、解決失敗を `MissingAnchor`（試行パスを保持）として返す（例外は投げない）。整形側は壊れたリンクを「動くリンクの偽装」にせず **素テキストで可視化**する — `link` は `[..](..)` で包まずエスケープ済み表示テキストのみ、`href` は空文字列を返す。表示テキストは残るので author は壊れた参照に気づいて直せる。なお `anchor_href` は解決済みノード専用で、`MissingAnchor` は整形フィルタ側が捌くため `anchor_href` には渡らない。

prose 例外の resolver 側挙動: マップは full anchor_path をキーにするフラットな dict ([generator.md](generator.md#anchor_path--%E3%83%8E%E3%83%BC%E3%83%89%E3%83%9E%E3%83%83%E3%83%97) の B2) なので、resolver はアンカーパスを分割せず**そのままキーで引く**。prose の `/` 素通しはアンカーパス構築側で吸収済みのため、resolver 側に prose 例外の特別扱いは要らない（例: `/prose/design/architecture` はそのキーで直に当たる）。

### 未決事項

- **空白を含む id の扱い**: HTML5 の `id` 属性は空白不可のため、空白を含む id はアンカーパス化不可。ビルド時に警告して当該 id 配下をアンカーパス無し扱いとする方針（[F4 / D 群と連携、未タスク化](../../../tasks.md)）
- **`toc:` プレフィックスの名前**: 実態は「アンカー参照」で TOC ではない。実装時（[B4, B5](../../../tasks.md)）に再検討する
