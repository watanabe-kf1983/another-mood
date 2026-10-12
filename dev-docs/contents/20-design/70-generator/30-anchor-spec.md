# Anchor Specification

データツリー上のノードの識別とリンク解決の仕様。ノードを一意に指す文字列を **アンカーパス** と呼ぶ。本ツールが対象とする文書ではページ間・項目間の相互リンクが多く、すべてのデータにアンカーパスを付与することでそれを安定して供給する。

## External Design

### 用語

- **ノード (node)**: データツリー上の一点 — レコード・ビューのグループ・シングルトン・ネストしたオブジェクト。リンクの宛先となる実体で、テンプレートでは `node()` で取得し `link` / `label` / `href` で整形する（[なぜ `node()` と呼ぶか](../../90-appendix/20-design/70-generator/30-anchor-spec.md#なぜリゾルバを-node-と呼ぶか)）
- **アンカーパス (anchor path)**: そのノードを一意に識別する文字列（データツリー上の住所）。本ツールが生成する。URL fragment として URL に埋め込まれる
- **アンカー (anchor)**: HTML/Markdown の anchor target（`<a id="…">`）。リンクを受け止めるページ上の標識で、id にはアンカーパスを使う。render が描画ノード（主題）に自動で刻むほか、`node | anchor` フィルタで手置きもできる（[アンカーの発行](#アンカーの発行) 参照）

### アンカーパス

アンカーパスは **データツリー上のパス** を `/` 区切りで表現した文字列。root を `/` とする **絶対パス形式**で、先頭の `/` が「データツリー root を起点とする絶対座標」であることを示す（相対参照と区別される）。

#### 構成

データツリーを root から目的のノードまで辿り、各ステップ（singleton 配下は dict キー、リスト要素はその `id` 値）を 1 セグメントとして書き出す。利用者向けの規則と例は `docs/reference/template.md` の Anchor paths、例の一覧は[付録](../../90-appendix/20-design/70-generator/30-anchor-spec.md#アンカーパスの例)。

リスト要素に `id` フィールドが無い場合（Array pattern で id を要求していないスキーマ）、その要素はアンカーパスを持たない。到達経路を表現する手段がないため、配下のオブジェクトもアンカーパスを持たない。Array 直下の Array も同様。

class（[schema-spec.md](../45-schema/10-schema-spec.md) の Entity ID および ObjectType ID）は schema 上の位置を示す **型レベルの識別子** で、データツリー上の実体パスであるアンカーパスとは直交する。class はアンカーパスの構築には登場しない。

#### 一意性

アンカーパスの一意性は **`id` の一意性に依存する**。同じ親の下に同じ id のレコードが 2 件あれば、両者のアンカーパスは文字列として一致し、[リンク](#リンクの両端)は片方にしか到達できない。一意性の単位が entity 全体ではなく兄弟集合なのは、アドレスが親のパスから合成されるからで、別の親の下の同じ id は別のノードを指す。

entity のデータについては、これを崩す入力を preprocess で検出できる。`content_normalizer` が全ソースの合流後に兄弟集合ごとの id 重複を検査し、見つかれば build を止める（合流後に見るのは、単体では妥当な 2 ファイルが合流して初めて衝突が生じるため）。

view については一意性を保証できず、保証を強制すべきでもない（[理由](../../90-appendix/20-design/70-generator/30-anchor-spec.md#view-の一意性を保証しない理由)）。検出は identity が実際に消費される時点まで遅らせ、**ページ主語として描画されたときに出力パスの衝突（`PageCollisionError`）としてのみエラーにする**。

#### Escape 規則

アンカーパスは **IRI**（RFC 3987）として扱う。URL fragment / パスとして使う以上 `/` を区切りに予約するため、**id 値が `/` を含む場合は percent-encoding (`%2F`) で escape する**（組み込みの `prose` / `blob` は例外、下記）。それ以外の文字は IRI エスケープで正規化し、生 Unicode を残す。アンカーパス（および由来する page_path）は URL であると同時に出力ファイルのパスでもあり、全非 ASCII を percent-encode すると CJK のsbdb プロジェクトで読めないファイル名になるためで、精密な条件と背景は[付録](../../90-appendix/20-design/70-generator/30-anchor-spec.md#escape-規則の精密な条件)。

escape 規則は文字単位の安全化までで、**文字単位で潰せない FS 固有問題**（パス長超過・Windows 予約名）はエスケープとは別に、パス書き出し側で対処する。

#### Prose / Blob の例外

**id 内の `/` は素通し** — 組み込みの `prose` / `blob` entity に限り、id 内の `/` を escape せずにアンカーパスへそのまま埋め込む。id が contents 相対パスで構造的に階層を持ち、flat な配列 entity なので曖昧性が生じないため（[理由](../../90-appendix/20-design/70-generator/30-anchor-spec.md#prose--blob-の例外の理由)）。

この例外は **組み込みコレクション（`prose` / `blob`）に固有** のものとして明示的に定義する。`/` を含む任意の id への一般化はしない — 利用者 entity は構造が変わりうるため、その id を素通しにすると将来曖昧性が混入する。

**見出しは `#slug` に畳む**（prose のみ） — prose 本文中の見出しは node（リンクの宛先）として扱う。データツリー上は prose レコード配下の `headings` リスト要素（[prose-spec.md の headings](../50-normalizer/25-prose-spec.md#headings--リンクの着地点)）で「ネストしたリスト要素 = node」規則に乗るが、anchor_path では中間の `headings` セグメントを畳み、**`<prose レコードの anchor_path>#<github-slug>`** とする（`/prose/X/headings/slug` でなく `/prose/X#slug`、例 `/prose/design/normalizer/architecture#エラー処理`）。見出しは別レコードではなく、prose レコード内の住所（着地点）だけを持つ。`#` が曖昧性を生まないことは[付録](../../90-appendix/20-design/70-generator/30-anchor-spec.md#prose--blob-の例外の理由)。

### ページ分割

**各ノードは *データ位置* で一意に定まる 1 ページにだけ描かれる。** どのページかは `render` の分割規則が決め、ページ内のどこかはテンプレートが決める。

#### 分割とインライン

`render` フィルタが主題の `_meta.object_type_id` を `file_per` と照合して分割/インラインを決めること、親ページのリンクは render が自動生成せず author が `| link` で書く two-loop パターン（分割なら別ページ URL・インラインなら同ページ `#fragment` に自動適応）は `docs/reference/template.md` の Split vs inline を正本とする。分割するのはノード主題だけで、スカラ主題は `file_per` に関わらず常に inline 展開するのは、ページはアンカーパスを持つノードであるべきだから（inline 展開は単なる差し込みなので任意の値を許す）。設計判断:

> **決定: 親リンクを render に畳み込まない.** リンク解決は既に `| link` ＋ page_path が持ち分割/インラインへ自動適応するので、render に持たせると二重実装になり、親側の周辺マークアップ（リスト記号等）も author の制御外になる。render の責務は「このノードの内容をどこに置くか」に保つ。

> **決定: インラインは型単位ポリシー（call-site 上書きは持たない）.** インライン意図は型を `file_per` から外して表現する。file_per 対象の型を call-site で `inline` 強制すると、そのノードが自前ページとインライン本文に**二重出力**され、`| link` の指す先と実体の所在がずれる（footgun）。

埋め込み先による見出し深さの調整は render 固有ではなく `under_heading` フィルタが担う（`docs/reference/template.md` の `under_heading`）。

#### 描画の単一ページ不変条件 (render subtree ガード)

[リンク解決](#リンク解決)は上の不変条件に乗っている: source は `page_path(this)`、target は `page_path(target)` — 両者が同じ規則でノードのデータ位置からページを引くからこそ、`| link` / `href` / `relink` が一貫して相対化できる。`render` フィルタで `this` の subtree 外にノードを inline 描画するとこの不変条件が破れ、`page_path(subject)` が実描画ページと食い違って、そのノードの内部 `this` 起点リンクも、そのノードへ張る被リンクも壊れる。

そこで render フィルタは、subject が `this` の子孫でなければ、描画元テンプレートのファイル付き（行は無い）のビルドエラーにする。判定は **構造（子孫）** で行い、split / inline や edition (file_per) に依存しない — 妥当性をテンプレート単体で決めたいため（同じ呼び出しが「split する edition では通り、しない edition では弾かれる」ような edition 依存エラーを避ける）。他所のノードを描きたいときはクエリ (join 等) で subtree に取り込んで子孫化するか、`| link` で参照する。非ノード subject の免除とその健全性の条件は `render_processor.py` の `_guard_subtree` docstring が正本。

### リンクの両端

テンプレートの `node()`（[テンプレートからの参照](#テンプレートからの参照)）から来ても本文の `node:`（[本文からの参照](#本文からの参照)）から来ても共通で、送り側（URL の fragment）と受け側（ページ上の id）が同じ文字列 — データノードは anchor_path、見出しノードは slug — を使うことで両端が構築上一致する。

出力する URL は **対象ページへの相対パス** + URL fragment。fragment は target がページ root に一致する場合も省かない（ハンドリングを単純に保つ）。blob ノードはページ上に描かれるノードではなく出力ツリー上の実ファイル（[blob-spec.md の出力配置](../50-normalizer/27-blob-spec.md#出力配置-アンカーパス--出力アドレス)）なので、fragment を持たずアンカーパスをそのままファイルパスとして相対解決する。URL の形は `docs/reference/template.md` の `href`。

#### アンカーの発行

一般のノードはページ上のどこに描かれるかをテンプレートしか知らないため、システムが着地点を任意に自動発行することはできない。ただし `render` フィルタ（およびルートテンプレート）は「この主題ノードを今ここに描く」ことを**システムが知っている唯一の経路**である。そこで描画はその主題のアンカー（`<a id="{anchor_path}">`）を出力の冒頭に自動で刻む（インラインはその場・分割/ルートはページ先頭）。これにより two-loop パターン（親が `| link`、子が分割/インライン）が、author の手置きなしに同ページ内 fragment 着地を成立させる。`| anchor` の手置きは、主題にせず本文で参照するだけのノード（テーブル行・リスト項目等）に着地点を与えるための escape hatch として残る。刻印は出力 format の `post_process` フック（`template_engine.py`、`md` は `stamp_anchor`）が全レンダ経路の単一の漏斗で行う。

**見出しノードには発行しない**。見出しの id は Goldmark/GitHub が native で打つので、システムが刻むと native id と重複 id になる。住み分けは **合成 id（ノード）は刻む／自然 id（見出し）は renderer 任せ** — 自動刻印・`| anchor` とも見出しには何も発行しない（[Prose / Blob の例外](#prose--blob-の例外)）。

着地点は raw HTML の `<a id>` なので、Hugo 側は bundled `resources/hugo/hugo.toml` の `unsafe = true` を要する（信頼前提は [unsafe HTML の信頼前提との整合](../../90-appendix/20-design/70-generator/25-template-trust-model.md#unsafe-html-の信頼前提との整合)）。

#### 未解決参照の扱い

`node()` の組んだパスがマップに無いとき、解決失敗を `MissingNode`（試行パスを保持）として返す（例外は投げない）。整形側は壊れたリンクを「動くリンクの偽装」にせず、表示テキストを角括弧で囲んだ **`[text]` の形で可視化**する。`link` / `href` / `anchor` / `relink` の各挙動は `docs/reference/template.md`、素テキストでなく角括弧を残す理由は[付録](../../90-appendix/20-design/70-generator/30-anchor-spec.md#未解決参照に素テキストでなく角括弧を残す理由)。`node` / `child` の住所を組み立てる引数が欠損したときは、参照そのものが成立しないので missing node にもならず、何も描かれない。

### テンプレートからの参照

テンプレートは **ノード** を `node()` で得て、`link` / `label` / `href` / `anchor` で整形する。呼び出しの記法と各フィルタの振る舞いは `docs/reference/template.md` の Linking / Filters / Functions を正本とし、ここには設計判断だけを置く。

- **escape の所在を呼び出し側から見せる**。`node(*segs, path=None, fragment=None)` はアンカーパスを三部品から組む: 位置引数は生の値を各 escape して後置、`path=` は出来合いのパスを verbatim に前置、`fragment=` は見出し slug を raw で末尾に付ける（[Prose / Blob の例外](#prose--blob-の例外)）。
- **誤用は例外にしない**。解決できないアンカーパスは MissingNode として可視化する（`/` 始まりの値を位置引数に渡せば `/%2F…` に escape され一致しない。[未解決参照の扱い](#未解決参照の扱い)）。
- **`anchor` は主題以外のノードに着地点を手置きする原始機能**。主題には自動刻印が刻む（[アンカーの発行](#アンカーの発行)）。
- **アンカーパス文字列だけを返す公開フィルタは置かない**（[経緯](../../90-appendix/20-design/70-generator/30-anchor-spec.md#anchor_path-フィルタを公開から外した経緯)）。
- **表示テキストは `title` → `name` → `id` → anchor_path 全体のチェイン**。「末尾セグメント」を fallback に入れないのは、それが意味を持つのはリスト要素か入れ子オブジェクトに限られ、一般化できないため。

### 本文からの参照

prose body 等の Markdown 本文では、リンク先に `node:` スキーム + アンカーパスを書いてノードを参照する（[scheme 名の背景](../../90-appendix/20-design/70-generator/30-anchor-spec.md#scheme-名を-node-とする背景)）:

```markdown
ユーザーの詳細は[ユーザー](node:/erds/user-management/entities/user)を参照。
```

この記法は二役を兼ねる:

1. **author 向け sugar** — author がノードを明示的に参照したいときの書き方。テンプレートの `node(path="/…") | link`（[テンプレートからの参照](#テンプレートからの参照)）の本文版で、解決後は同じ `[display](URL)` になる
2. **canonical intermediate form** — Normalizer がソース相対リンクから変換した先の中間表現

ソース Markdown では普通の相対パスで書け、Normalizer が `node:` 記法に変換する ([prose-spec.md の content](../50-normalizer/25-prose-spec.md#content--ソースそのまま相対リンクだけ-node-化) 参照):

```markdown
{# ソース: {contents_dir}/design/normalizer/normalizer.md #}
[Composer](../composer/composer.md)
↓ Normalizer が変換 ↓
[Composer](node:/prose/design/composer/composer)
```

見出しは `node:/prose/X#slug` の fragment で運び、ソース相対リンクの `#fragment` も Normalizer が透過で運んでこの形になる。`relink` はこの文字列全体を見出しノードとして解決する（記法は `docs/reference/template.md` の Anchor paths / `relink`）。

#### 対象はインラインリンク形のみ

`[text](node:…)` のインライン形（画像 `![alt](node:…)` を含む）だけを解決する。参照形（`[text][label]` + 別行 `[label]: node:…`）と autolink（`<node:…>`）、title 付き `[text](node:… "title")` は **恒久的に非対応**（後回しの deferral でなく非ゴール）。理由:

- Normalizer のリンク正規化が生成するのはインライン形のみ。参照・autolink が出るのは手書きの場合だけで、実利用上の頻度はきわめて小さい（インライン ≫ 参照 > autolink）
- autolink は素だと表示テキストが URL になり、参照形は未解決時の plain 化が「リンク位置」と「定義行」に跨って綺麗に畳めない — どちらも対応コストに対し需要が薄い
- 利用者には「手書きの `node:` 参照はインライン形で書く」と案内すれば足りる

#### `relink` は著者が明示適用する

本文の `node:` リンク先を表示先ページからの相対 URL に置換する `relink` は、**リンク解決の単一責務**に絞り、見出し深さ調整は `under_heading` と合成する（`{{ prose.content | relink | under_heading("##") }}`。仕様は `docs/reference/template.md` の `relink`）。

relink は author が明示的に書く (`{{ prose.content | relink }}`) のを設計とし、システムが暗黙に挟む案は採らない。値単位で挟める自動フックは `template_engine.py` の finalize しかない（`post_process` はページ単位の post-render 置換で、[リンク解決](#リンク解決)のとおり採らない）が、finalize は `Markup` を素通しする一方、`under_heading` 等の Markdown 出力フィルタはその `Markup` を返す。ゆえに暗黙 relink は `under_heading` と合成した瞬間に発火せず、`node:` を silent に出力へ漏らす (値に「relink 未了」の印を持たせて伝播させる代案も、文字列連結・Markup 化で印が黙って落ちるため信頼できない)。明示適用は raw な `node:` content の直近に author が relink を置くから確実で、合成順序も `| relink | under_heading` と見えるまま残る。

## Internal Design

### ノードメタデータ

Composer が渡す木は純粋なデータで、ノードは自分が木のどこにいるかを知らない。木をページに割り、ページ間をリンクで繋ぐには、任意のノードについて三つの問いに答える必要がある: **住所**は何か（リンクの着地先とページパス）、**どの型**か（`file_per` による分割と、由来型ごとのアンカーの刻み方）、**容れ物**は何か（住所の親からの合成と、`render` の subtree ガード）。Generator はその答えをシステム由来のフィールドとして、各ノードの、テンプレートからは直接読み取れない場所に注入する。

| フィールド | 答える問い | 読む側 |
|---|---|---|
| `_parent` / `_parent_record` | 容れ物: データツリー上の直近の親ノード / 最も近い Mapping 祖先（間の Array を 1 段飛ばす。Mapping のみ） | アンカーパスの合成、`render` の subtree ガード |
| `_meta.anchor_path` | 住所: このノードのアンカーパス | `href` / `link` フィルタ、[ページパスの導出](#ページパスの導出)、`<a id>` 刻印 |
| `_meta.fragment` / `_meta.stamps_anchor` | リンクの着地 fragment と `<a id>` 刻印の要否（由来型ごとの anchor strategy が決める） | `href` / `anchor` フィルタ |
| `_meta.object_type_id` | 型: スキーマ位置を表すカタログ形 ID（Array 要素は `X.item`、singleton は `X`、Array は `X.item[]`） | `file_per` 判定、anchor strategy の選択 |

テンプレートはこれらの値をフィルタ経由で使う。`_` prefix はデータ側のキーを影にしないための予約（[なぜ直接触らせないか](../../90-appendix/20-design/70-generator/30-anchor-spec.md#なぜメタデータをテンプレートから直接触らせないか)）。

ラップ対象（id 無し Array 要素・ネスト Array は inert container のまま除外）、`_parent` / `_parent_record` の二系統セマンティクス、`anchor_path` / `_type_path` の `cached_property` による再帰合成（amortized O(depth)）、prose 例外といった厳密な規則は `data_tree.py` の docstring が正本。

### ページパスの導出

ノードの**表示先ページのパス** (レポートルート相対、fragment 抜き) を求める。page_path は **`(node, file_per)` の関数**であってノード単体の内在属性ではないため `_meta` には焼かない — 消費側 (リンク解決フィルタ、`render` フィルタ) が render ごとに `PagingPolicy` を受け取り、必要時に `paging.page_path(node)` を呼ぶ。

paging ポリシーは `PagingPolicy` が担い、構造的な木の遡上だけは data_tree の free function `nearest_ancestor` に分離する (`PagingPolicy` は paging を知らない木に触れず、data_tree は paging を知らないまま保つ)。導出規則と座標系の理由は `edition.py` の `PagingPolicy` docstring が正本。

### リンク解決

リンク解決はアンカーパスからノードを引く `{anchor_path: node}` のフラットなマップ（`data_tree.py` の `build_node_map`）の上に立ち、pre-render 段階で完結する (post-render の文字列置換は採らない)。ヘルパは依存方向で 2 群に分かれる: フォーマット非依存の中立ヘルパ (`node` global、`child` / `label` フィルタ) はノードマップだけに束縛され、フォーマット固有の `link` / `href` / `relink` は `PagingPolicy` に束縛される（`relink` はノードマップも引く。`anchor` は束縛を持たない）。source ページ（主題ノード）は render state の `this` から得る。

実装契約（`@pass_state` の要否、`MissingNode` の捌き方）は `data_tree_filters.py` / `output_formats/md.py` の docstring、[リンクの両端](#リンクの両端)の fragment 規則と stamp 可否をノードの由来型で選ぶ anchor strategy は `data_tree.py` の `_Anchor` 各クラス、`relink` が本文中の本物の `node:` リンクを見つけて splice する機構は `shared/markdown.py` の docstring が正本。

## Proposals

### 未決事項

- **未解決参照のビルドレポート警告**: `link` / `relink` とも未解決参照は `[text]` で可視化するのみで、ビルドレポートには積まない。両フィルタ共通の経路で警告に載せる
- **一意でないアンカーパスの扱い**: NodeMap はアンカーパスをキーとする dict で、一意でないノードは後勝ちに畳まれる（view では[一意性](#一意性)のとおり正当に起こる）。構築時に検出してそこへのリンクを抑止する、あるいは警告する余地はあるが、`PageCollisionError` の手前でどこまでやるかは未検討
