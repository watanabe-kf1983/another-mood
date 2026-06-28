# Paging Specification

ファイル分割戦略の仕様。ドキュメントのページ分割と edition の出し分けを定義する。

## External Design

### レポート設定ファイル

`definition/reports.yaml` でレポート出力を設定する。`schema.yaml` と並ぶ必須ファイル。`mood init` および各 blueprint が生成する。

`file_per` にはページとして切り出す対象 ObjectType ID ([schema-spec.md](../normalizer/schema-spec.md#entity-名) 参照 — 実行時には各ノードの `_meta.object_type_id` ([generator.md](generator.md#ノードメタデータ)) と照合される) を列挙する:

```yaml
# definition/reports.yaml
file_per:
  - erds.item
  - erds.item.entities.item
```

形式検証は内蔵の `reports-schema.yaml` で行う。

### テンプレート主題のノード受け取りと `this` 束縛

テンプレートの主題（subject）は **データツリーのノード**（Mapping = レコード / Array = コレクション）として渡し、コンテキストに **固定名 `this` で束縛**する:

- **Mapping 主題**: キーを spread し `{{ 名前 }}` で bare アクセス（`this.` 税ゼロ）。加えて `this` も束縛（`{{ this.名前 }}` ≡ `{{ 名前 }}`）
- **非 Mapping 主題（Array）**: spread するフィールドがないので `this` のみ（`{% for e in this %}`）
- スカラ主題は、分割（別ページ書き出し）時のみエラー — ページはアンカーパスを持つノードであるべきだから。inline 展開は単なる差し込みなので任意の値を許す
- `this` は型不問で **常に主題ノード自身**（`_meta` アクセス・配列反復の handle）

**束縛はレンダリング境界（`template_engine._bind`）の単一規則**として、root テンプレート（`index.md`）と `{% mood_view %}` サブテンプレートに同一に適用する。利用者から見えるデータモデルがツリー全体で一致し、root も自ノードを `this` で参照できる。`{% mood_view %}` 側はパス決定とノードのパススルーだけを担い、context 構築は持たない。

加えて、主題が `this` でノードとして取れることはリンク解決の足場でもある — source ページ（主題ノード）を `this` から得られるので、resolver は per-render の source-node 束縛を持たず静的な `(Edition, node_map)` だけを束縛すればよい（[generator.md のリンク解決](generator.md#リンク解決)）。

### 分割ルール

`{% mood_view "tpl" with NODE %}` は主題ノードの `_meta.object_type_id`（[generator.md](generator.md#ノードメタデータ)）を `file_per` と照合して振る舞いを決める:

- **`file_per` の分割単位に含まれる** → 別ページに書き出し、**呼び出し位置には何も残さない**（`render_to_file` して空文字列を返す）
- **含まれない** → その場にインライン展開（`{% include %}` 相当）

親ページ側に出すリンクや目次は **mood_view が自動生成しない**。author が `| link` で別途書く。`| link` は target の page_path（[ページパスの導出](generator.md#ページパスの導出)）で解決されるので、**分割なら別ページ URL・インラインなら同ページ内 `#fragment`** に自動で適応する。これにより author は分割/インラインを意識せず、同じテンプレートが Web 用（分割）でも PDF 用（全インライン）でも動く。

典型は **TOC ループと内容ループの分離**（two-loop パターン）:

```jinja2
{# 親ページの目次: 常にリンクを出す（分割なら別ページ、インラインなら #fragment へ適応） #}
{%- for member in members %}
- {{ member | link }} — {{ member.role }}
{%- endfor %}

{# 内容: 分割ならページ書き出し、非分割ならインライン展開 #}
{%- for member in members %}
{%- mood_view "member.md" with member %}
{%- endfor %}
```

> **背景: なぜ自動リンクを mood_view に持たせないか.** 当初案は「分割時に親へリンクを残す」だったが、リンク解決の責務は既に `| link` ＋ page_path にあり、しかも分割/インラインへ自動適応する。mood_view にリンク生成を畳み込むと二重実装になり、かつ親側の周辺マークアップ（リスト記号・付随情報）を author が制御できなくなる。mood_view の責務は「このノードの内容をどこに置くか」の一点に保つ。`{% mood_view %}` にブロック本体やアーム（`{% split %}` 等の発明語）を持たせる糖衣も検討したが、two-loop パターンが既知の素の構文だけで同じことを達成するため採らない。

> **背景: per-call-site インライン上書きは持たない（`inline` キーワードを廃止）.** 旧 `{% mood_view ... inline %}` は file_per 機構導入前の唯一のインライン手段だったが、file_per 導入後はインライン意図を **型単位ポリシー（file_per から外す）**で表現でき、call-site 上書きとの併存は footgun を生んだ: file_per 対象の型を call-site で `inline` 強制すると、そのノードが「自前ページ」と「インライン本文」に**二重出力**され、`| link` の指す先と内容の所在がずれる。よってインラインは型単位の一手段に統一した。将来 per-instance 需要が出たら別機構で入れ直す。

> **見出し深さ.** subtemplate が「見出し＋本文」を一単位で再利用したいとき、埋め込み先によって見出しレベルが変わる（同じ型を `##` 下でも `###` 下でも置きたい）。この深さ調整は mood_view 固有ではなく、生成側の `under_heading` フィルタ（任意の埋め込み出力をブロックで囲む／prose body をパイプで処理）が担う。split 時に mood_view が `""` を返す性質と合わさり、同じ記述が分割でもインラインでも正しく出る。仕様は [docs/reference/template.md の `under_heading`](../../../../docs/reference/template.md#under_heading) を参照。

### ページパスと出力ディレクトリ

ページパスはアンカーパスから直接導出される。導出規則は `Edition.page_path` が持ち、その定義は [generator.md](generator.md#ページパスの導出) を正本とする。anchor_path を流用するため、セグメントの**エスケープも anchor_path と同じ IRI 形を継承する**（[anchor-spec.md](anchor-spec.md#escape-規則) — 非 ASCII の `ucschar` は生のまま、`/` 等の構造文字と FS 危険文字は percent-encode）。要点:

- **非 root**: anchor_path の先頭 `/` を落として `.md` を付けたもの（例: `/erds/user-management` → `erds/user-management.md`、`/erds/user-management/entities/user` → `erds/user-management/entities/user.md`、シングルトン `/overview` → `overview.md`）
- **root (`anchor_path == "/"`)**: `index.md` 固定（file_per 不問）

これによりアンカーパス規則と paging path 規則が同じ shape で表現される。

`page_path` は **edition ルート相対**。実ファイルの書き出し位置は mood_view が edition のマウント先（`{outDir}/{edition}/`）を被せて決める（`{outDir}/{edition}/{page_path}`）。現状の単一構成（form A）では暗黙 edition `default` が唯一の edition なので `{outDir}/default/{page_path}` に出る。各 edition ディレクトリは `{outDir}` 直下に置かれ、同じく `{outDir}` 直下に出る診断系出力（`index.md`、`__entity_defs/` 等）と横並びになる:

```
{outDir}/
  index.md                                     ← メタ index（入口。各 edition を列挙）
  default/   (form B なら web/ pdf/)            ← edition（report 本体）
  __entity_defs/  __entity_data/  __queries/   ← 診断（edition 横断・常に同位置）
```

診断系は `__` 予約済みなので edition 名と衝突せず、edition 横断で常に同じ位置に出る。

> **背景: リンク層を触らずに済む.** リンク URL は page 相対（`node_href` は source ページから target ページへの relpath、[generator.md のリンク解決](generator.md#リンク解決)）なので、`{edition}/` のマウント接頭辞はリンク解決に対して透過。各 edition が自分の `file_per`（→自分の `page_path`）で解いた相対 URL がそのまま正しく、リンクフィルタ層に改修は要らない。各 edition は自己完結した相対リンクのサブツリーになる。

> 複数 edition（`editions:` = form B）を 1 ビルドで横並びに出す構成は [Proposals](#editions-c6) 参照（form A はその単一形）。

## Internal Design

### meta 診断の分割

meta 診断ページ（`__entity_defs` / `__entity_data` / `__queries`）の主題は **実データツリーノード**で、専用のビルトインクエリ（`src/another_mood/resources/queries/`）が生む。`{% mood_view %}` の分割判定は一様で、[分割ルール](#分割ルール)そのもの — **主題が実ノードかつ `object_type_id` が file_per 対象なら分割、それ以外はインライン**（予約マーカーも template-keyed fallback も無い）。

主題ノードを生む 3 クエリ:

- `__entity_defs` / `__entity_data` — どちらも `from: __definition.entities`（`view: false`・ルート entity）で**同じ entity 集合**を引くが、**別クエリ＝別アンカールート**（`/__entity_defs/{id}` と `/__entity_data/{id}`）。同一 entity を Definition と Data の **2 ページ**に出すのに、クエリ名でアンカーを分けることで one-node-two-pages 衝突を避ける（差は select のみ: 前者 `id`+`builtin`、後者 `id`）。
- `__queries` — `__definition.queries` の passthrough（`select` 省略）。各アイテムが query 定義の全フィールドを持ち、テンプレートがそのまま描画する。

meta レンダリングには利用者の `reports.yaml` が無いので、分割は **固定の内部 file_per**（`meta_templates.META_EDITION` = `__entity_defs.item` / `__entity_data.item` / `__queries.item`）で駆動する。各結果アイテムの anchor_path `/{view}/{id}` から通常の page_path 規則で `{view}/{id}.md` が導かれる — **1 ノード 1 ページ**。共有コンテキストである data root と schema は、子テンプレが anchor_path で直接引く（root = `node("/")`、schema = `node("/__definition/entities")`。`node` は anchor_path→node 解決の global で、`build_node_map` が全 wrap ノードを anchor_path で索けるようにするため成り立つ）ので、主題ノードは identity フィールドだけを持てばよい。

> **背景: 別ページが要るならノードを一つ立てる.** 旧実装は `__root.md` 内で合成 dict（アンカーパス無し）を組み、予約キー `_split` ＋ template-keyed fallback（`{template_stem}/{id}.md`）で分割していた。これは「1 ノード→複数ページ」を fallback がテンプレート名で曖昧性を割る誤魔化しで、**one-node-one-page ポリシー違反**だった。別ページが要るならノードを一つ立てる — 同一 entity に 2 ページ要るなら `__entity_defs` と `__entity_data` の 2 ノードを立てる、というのがこの原則の実践で、`_split` マーカーと fallback は撤去された。

> **残: 出力ディレクトリの集約（F9）.** これら `__{view}/` は今も output 直下に横並びで散る。単一ディレクトリ配下への集約は F9 が担う。

### メタ index の edition 列挙

メタ index（`{outDir}/index.md`）の `## Reports` は各 edition を名前でリンクする（form A は `[default](default/)`）。edition 名の列は generator がモデルの最上位 `__` メタチャネルに `__edition_names` として注入し（`__definition` 等と同経路で、ルート直下の配列ノード `/__edition_names` になる）、テンプレートは `__entity_*` と同じ素アクセス（`{% for name in __edition_names %}`）で反復する — global 配線も `reports.yaml` 依存も持たない。form B で edition が増えても列が伸びるだけでテンプレ無改修。edition 横断の landing ページは作らず、入口はメタ index に集約する。

## Proposals

> 残タスク: Editions form B (C6)、meta 出力ディレクトリの集約 (F9)。C5（form A を単一 edition `default` に出す破壊的フリップ）は実装済みで、出力ディレクトリ規約は [External Design](#ページパスと出力ディレクトリ)、メタ index の列挙は [Internal Design](#メタ-index-の-edition-列挙) に移設済み。

### Editions (C6)

1 つの report を複数の **edition**（Web 版・印刷版を並行配信する等）で出すために、`editions:` キーで列挙する形を追加する。edition は同一 report の体裁違いで、**当面 edition 間の差は `file_per`（分割粒度）のみ** — Markdown→HTML レンダリングは全 edition 同一で、別レンダラ・別フォーマットは持たない（"pdf" edition も「全インラインの 1 ページ」を通常どおり HTML で出すだけ）。全 edition は 1 ビルドで同時に生成し `{outDir}/{edition}/` に横並びで公開する（環境で 1 つ選ぶ "profile" ではない）。

#### 設定ファイルの二択 form

`definition/reports.yaml`（ファイル名は不変 — report の出力設定）は次の二択。**混在は不可**（トップに共通設定を書きつつ `editions:` でも書く形は禁止）:

```yaml
# form A: トップ直書き（単一 edition）— 現行
file_per:
  - erds.item
  - erds.item.entities.item
```

```yaml
# form B: editions
editions:
  web:
    file_per:
      - erds.item
      - erds.item.entities.item
  pdf:
    file_per: []              # 分割なし → 全部 index.md にインライン
```

- 各 edition エントリの中身は form A のトップと同型（現状 `file_per` のみ）。
- form A は **暗黙の単一 edition**で、その edition 名は `default`（出力 `{outDir}/default/`）。
- 空の `editions: {}` は不可（最低 1 edition）。
- edition 名は出力ディレクトリのセグメントになる。検証は**ゆるく**（非空文字列）、セグメント化時に page_path / anchor_path と同じ IRI エスケープ（[anchor-spec.md](anchor-spec.md#escape-規則)、B7）を被せて FS-safe にする。唯一 `__` 始まりだけは診断ディレクトリ（`__entity_defs/` 等）と outDir 直下で衝突するため禁止する。FS 固有のキツいエッジ（長さ・予約名等）は C7 に委ねる。

形式検証は内蔵 `reports-schema.yaml` の `oneOf`（form A ⊕ form B）で行う。

> 出力ディレクトリ規約（`{outDir}/{edition}/` への出力、診断系の edition 横断配置）と、メタ index の `## Reports` 列挙（`__edition_names`）は C5 で実装済み。設計は [External Design](#ページパスと出力ディレクトリ) / [Internal Design](#メタ-index-の-edition-列挙) を正本とする。form B はこの規約に edition を複数並べる加算拡張。

#### Edition と逐次生成 (C6)

骨格は ① の無影響リファクタで実装済み: `Edition`（`name` / `file_per` / `page_path` / `is_split_target` のドメイン型、`edition.py`。meta 用の固定 edition は `META_EDITION`）と、`load_editions(reports_file) -> Sequence[Edition]` ＋ `generate()` の**逐次**ループ（各 `edition` を `{outDir}/{edition.name}` へ、`make_link_filters(edition, node_map)` を束ねて render）。form A は `[Edition(name="default", file_per=[...])]` の単一要素を返す。

残る C6 は **form B の取り込み**:

- `load_editions` に form B 分岐を足し、`editions:` マップを `[Edition(name="web", ...), Edition(name="pdf", ...)]` に展開する。
- `reports-schema.yaml` を form A ⊕ form B の `oneOf` にする。edition 名検証（非空・`__` 始まり禁止・セグメント化時の IRI エスケープ）は上記 [設定ファイルの二択 form](#設定ファイルの二択-form) のとおり。
- "並列ビルド" は成果物が横並びに出る意で concurrency は持ち込まない。単一 edition 選択（`--edition`）も当面持たない。

> **残: CLI watch バナーの edition 一般化（C6）.** `mood watch` 起動時の `Reports: {base}/default/`（`cli.py`）は form A 前提で `default/` を直書きしている。form B では存在しない名前を指すので、メタ index（`{base}/` が各 edition を列挙）へ向けるか edition を列挙する形へ一般化する。

### Edition 別ルートテンプレート（将来）

将来、edition ごとに異なるルートテンプレート（`index.md` 以外）を指定したい需要がある（Web 版と印刷版でトップ構成を変える等）。これは `file_per` と同じ `Edition` の継ぎ目に `root_template` 等のフィールドを足し、`generate()` のループ本体で render するルート名を差し替えるだけで乗る加算的拡張で、editions (C6) のスコープからは外す。継ぎ目を保つため、ルートテンプレート名 `"index.md"` を `generate()` の奥にハードコードし続けず `Edition` 由来にできる形を意識する（現状は `"index.md"` 固定）。
