# Anchor Specification

データツリー上のノードの識別とリンク解決の仕様。ノードを一意に指す文字列を **アンカーパス** と呼ぶ。

## External Design

### 用語

- **ノード (node)**: データツリー上の一点 — レコード・クエリのグループ・シングルトン・ネストしたオブジェクト。リンクの宛先となる実体で、テンプレートでは `node()` で取得し `link` / `label` / `href` で整形する
- **アンカーパス (anchor path)**: そのノードを一意に識別する文字列（データツリー上の住所）。本ツールが生成する。URL fragment として URL に埋め込まれる
- **アンカー (anchor)**: HTML/Markdown の anchor target（`<a id="…">`）。リンクを受け止めるページ上の標識で、id にはアンカーパスを使う。発行は未実装 — [アンカー発行フィルタ (構想)](#アンカー発行フィルタ-構想) を参照

> **背景: 語彙の振り直し — 旧「ノード = アンカー」定義の廃止.** 当初は「リンクされ得る対象」をアンカーと呼んでデータツリー上の各ノードと同一視し、リゾルバ関数も `anchor()` と命名していた。しかし `link` / `label` / `href` は「ノードを受けて、そのノードの何かを描画する」フィルタ族で、アンカーターゲット (`<a id>`) を描画する将来フィルタの自然な名前は `data | anchor` — `<a id>` / `<a href>` の両面が `anchor` / `href` という対の名前で揃う。そこで anchor の語は HTML 本来の意味（受け側の標識）に予約し、リゾルバは「アンカーパスを解決して得られるもの」の名 — ノード — で `node()` とした。node / data tree は利用者向けリファレンス (docs/reference/template.md の Anchor paths 節) が先行して採用していた語彙でもある。rename の対応表は [語彙の振り直しと rename (B8)](#語彙の振り直しと-rename-b8) を参照。

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

テンプレート内では **ノード** を `node()` で得て、整形フィルタで仕上げる:

```jinja2
{{ node("erds", erd.id, "entities", entity.id) | link }}
{# segments からノードを解決 → [<display>](<URL>) の Markdown リンク #}

{{ node("/erds/user-management/entities/user") | link }}
{# 第一引数が `/` 始まり → 出来合いのアンカーパスとして解決（prose / 定数）#}

{{ member | link }}
{# すでに手にあるノードはそのまま整形できる #}

{{ node("erds", erd.id) | label }}   {# 表示文字列のみ #}
{{ node("erds", erd.id) | href }}    {# URL のみ #}
{{ member | link("ER 図") }}         {# display text を明示 override #}
```

- `node(seg, *segs)` — segments（各セグメントを escape）か、`/` 始まりの出来合いアンカーパスから、**ノード**を得る。関数形・フィルタ形（`"/..." | node`）の両用。第一引数の `/` 始まりで raw 判定するのは安全 — エンティティ/クエリ名は識別子パターン（`/` 始まり不可、schema-schema / query-schema の `propertyNames`）に縛られるため。1 引数 = 1 セグメント（`/` 入りを 1 引数に混ぜない）。
- `link` / `label` / `href` — ノード → Markdown リンク / 表示文字列 / URL。

アンカーパス**文字列**だけを返す公開フィルタは置かない。当初 `anchor_path(seg, *segs)` として公開していたが実需が一度も現れなかったため公開名から外した — 実需が出たら概念名と同じ `anchor_path` の名で再導入する（構築関数は内部に保持）。

display text は対象ノードから `title` → `name` → `id` → anchor_path 全体 のチェインで解決する。「末尾セグメント」を fallback に入れないのは、それが意味を持つのはリスト要素か入れ子オブジェクトに限られ、一般化できる fallback ではないため。`link(arg)` のように引数で渡せば override。

#### 出力 URL の形式

出力する URL は **対象ページへの相対パス** + URL fragment。例: `[ユーザー](../erds/user-management.md#/erds/user-management/entities/user)`。

- **path 部**: source ページから target ページへの相対パス
- **fragment 部**: target ノードの anchor_path をそのまま使う (full anchor_path 形式)。常に付与する (target がページ root に一致する場合も省かない — ハンドリングを単純に保つ)。受け側の HTML id は未発行 — [アンカー発行フィルタ (構想)](#アンカー発行フィルタ-構想) が同じ文字列で `<a id>` を置く想定で、それまで fragment はページ内ジャンプとしては機能しない（ページ単位のリンクは path 部で機能する）

#### 未解決参照の扱い

`node()` の組んだパスがマップに無いとき、解決失敗を `MissingNode`（試行パスを保持）として返す（例外は投げない）。整形側は壊れたリンクを「動くリンクの偽装」にせず **素テキストで可視化**する — `link` は `[..](..)` で包まずエスケープ済み表示テキストのみ、`href` は空文字列を返す。表示テキストは残るので author は壊れた参照に気づいて直せる。

## Internal Design

### リンク解決

リンク解決の内部配線はこの文書では持たない。フィルタの 2 群構成（中立 `node` / `label` とフォーマット固有 `link` / `href`）・供給経路・レポートルート相対の座標系・page_path / URL をノードに焼かない判断は [generator.md のリンク解決](generator.md#リンク解決-b4-b5) と [ページパスの導出](generator.md#ページパスの導出-b6) を正本とする。実装レベルの契約 — `@pass_context` が要る二つの理由（source 取得と定数畳み込み抑止）、`MissingNode` を整形フィルタ側で捌き `node_href` には渡さないこと — は `generator/data_tree_filters.py` と `generator/output_formats/md.py` の docstring に残している。

## Proposals

### アンカー発行フィルタ (構想)

> **未タスク化** — 実需が出た時点でタスク化する。

`data | anchor` — ノードを受けて、その場にアンカーターゲット（`<a id="{anchor_path}">`）を描画するフィルタ。`link` / `label` / `href` と同じ「ノードを受けて描画する」族に対称的に収まり、`href` が常時付与している fragment（[出力 URL の形式](#出力-url-の形式)）の受け側を発行する — 片側だけ実装済みの契約の残り半分。ノードの内容がページ上のどこに描かれたかはテンプレートしか知らないため、システムの自動発行ではなく author がフィルタで置く。出力はフォーマット固有なので md 側（`OutputFormat.link_filters` 経由）に属する。

### 語彙の振り直しと rename (B8)

> **設計合意済・未適用** — Phase 11 タスク [B8](../../../tasks.md)。実装セッションは本節の対応表を正本として適用し、完了時に本節を削除する。本文書と generator.md の External / Internal Design は振り直し後の語彙で記述済み（適用までコードと一時的に不一致）。

[用語](#用語)の背景に記した語彙の振り直しに伴う rename。**出力はバイト同一のはず** — showcase 3 種（starter / music / japanese-table-design）と dev-docs をビルドし、適用前と一致することを検証する。

#### テンプレート公開名

| 現在 | 変更後 |
|---|---|
| `anchor(seg, *segs)`（関数・フィルタ） | `node(seg, *segs)`（入力規則は据え置き） |
| `anchor_path(seg, *segs)`（関数・フィルタ） | 削除（実需が出たら同名で再導入） |
| `link` / `label` / `href` | 据え置き |

#### 内部名

原則: **実体を指す名前は node に従い、住所文字列を指す名前は anchor_path に残り、`<a>` 標識を指すときだけ anchor を使う**。

| 現在 | 変更後 |
|---|---|
| `generator/anchor.py` | `generator/data_tree_filters.py`（data_tree 上のテンプレートフィルタ、の意） |
| `make_anchor_filters` | `make_data_tree_filters` |
| `resolve_anchor` | `resolve_node` |
| `MissingAnchor` | `MissingNode` |
| `anchor_label` / `anchor_href` | `node_label` / `node_href` |
| `build_anchor_map`（data_tree.py） | `build_node_map` |
| `anchor_map`（引数・変数。generator.py のローカル `anchors` 含む） | `node_map` |
| `build_anchor_path` | **据え置き**（作るものが anchor path 文字列そのもの） |

#### 触らないもの

- `_NodeMeta.anchor_path` / `_meta.anchor_path` / 診断列ラベル `_anchor_path`（meta テンプレート含む）— anchor path は概念として存続（[用語](#用語)）。`anchor_` 接頭辞は page path との判別に実働している
- ID 体系・エスケープ規則（本文書 External Design）と `generator/url.py` の `url_escape`
- B5 の仮称 `resolve`（`node` 採用で語彙衝突は消滅。名前の再検討は B5 実装時のまま）

#### 追従箇所

- テンプレート呼び出し 8 箇所 — showcase: starter/by_role.md、music/index.md ×2、music/artist-detail.md / dev-docs: index.md、roadmap.md、tasks.md ×2
- `docs/reference/template.md` — カタログ表と Functions 節（`anchor` → `node`、`anchor_path` 項の削除、Filters 節導入行）。docs/ は実装済み機能のみを載せるため、rename 適用と同じ PR で更新する
- `docs/guides.md` / `docs/reference/reports.md` のインバウンド参照（`#anchor` 系見出しアンカー等）の確認
- テスト — `tests/components/generator/test_anchor.py` → `test_data_tree_filters.py`、`test_md.py` / `test_template_engine.py` 内の参照
- 検証 — `make ci` + showcase / dev-docs ビルド出力の同一性確認

### Markdown 本文中のアンカー参照

> **未実装** — Phase 11 タスク [B5](../../../tasks.md)（prose body `resolve` フィルタ）。リンク解決・整形フィルタ (B4) は実装済み — External / Internal Design 節を参照。

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

### prose body 処理フィルタ（仮称 `resolve`）

prose body 中の `toc:` URL を実 URL に置換する pre-render フィルタ。anchor 解決以外にも見出しレベル正規化やエスケープ調整等を兼ねる総合処理フィルタとする。

### 未決事項

- **空白を含む id の扱い**: HTML5 の `id` 属性は空白不可のため、空白を含む id はアンカーパス化不可。ビルド時に警告して当該 id 配下をアンカーパス無し扱いとする方針（[F4 / D 群と連携、未タスク化](../../../tasks.md)）
- **`toc:` プレフィックスの名前**: 実態は「アンカーパス参照」で TOC ではない。実装時（[B5](../../../tasks.md)）に再検討する
