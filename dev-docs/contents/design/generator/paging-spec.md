# Paging Specification

ファイル分割戦略の仕様。ドキュメントのページ分割とプロファイル切り替えを定義する。

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

加えて、主題が `this` でノードとして取れることはリンク解決の足場でもある — source ページ（主題ノード）を `this` から得られるので、resolver は per-render の source-node 束縛を持たず静的な `(ReportsConfig, node_map)` だけを束縛すればよい（[generator.md のリンク解決](generator.md#リンク解決)）。

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

ページパスはアンカーパスから直接導出される。導出規則は `ReportsConfig.page_path` が持ち、その定義は [generator.md](generator.md#ページパスの導出) を正本とする。anchor_path を流用するため、セグメントの**エスケープも anchor_path と同じ IRI 形を継承する**（[anchor-spec.md](anchor-spec.md#escape-規則) — 非 ASCII の `ucschar` は生のまま、`/` 等の構造文字と FS 危険文字は percent-encode）。要点:

- **非 root**: anchor_path の先頭 `/` を落として `.md` を付けたもの（例: `/erds/user-management` → `erds/user-management.md`、`/erds/user-management/entities/user` → `erds/user-management/entities/user.md`、シングルトン `/overview` → `overview.md`）
- **root (`anchor_path == "/"`)**: `index.md` 固定（file_per 不問）

これによりアンカーパス規則と paging path 規則が同じ shape で表現される。

`page_path` は **レポートルート相対**。実ファイルの書き出し位置は mood_view が出力ディレクトリ規約のマウント先（`{outDir}/reports/`）を被せて決める（`{outDir}/reports/{page_path}`）。`{outDir}` 直下の診断系出力（`index.md`、`__entity_defs/` 等）はマウント先と無関係に常に同じ位置に出る。

> 複数プロファイル（[Proposals](#複数プロファイル)）を入れると、`reports/` の下に `{profile_name}` 軸が一段挟まる（`{outDir}/reports/{profile_name}/{page_path}`）。

## Internal Design

### meta 診断の分割

meta 診断ページ（`__entity_defs` / `__entity_data` / `__queries`）の主題は **実データツリーノード**で、専用のビルトインクエリ（`src/another_mood/resources/queries/`）が生む。`{% mood_view %}` の分割判定は一様で、[分割ルール](#分割ルール)そのもの — **主題が実ノードかつ `object_type_id` が file_per 対象なら分割、それ以外はインライン**（予約マーカーも template-keyed fallback も無い）。

主題ノードを生む 3 クエリ:

- `__entity_defs` / `__entity_data` — どちらも `from: __definition.entities`（`view: false`・ルート entity）で**同じ entity 集合**を引くが、**別クエリ＝別アンカールート**（`/__entity_defs/{id}` と `/__entity_data/{id}`）。同一 entity を Definition と Data の **2 ページ**に出すのに、クエリ名でアンカーを分けることで one-node-two-pages 衝突を避ける（差は select のみ: 前者 `id`+`builtin`、後者 `id`）。
- `__queries` — `__definition.queries` の passthrough（`select` 省略）。各アイテムが query 定義の全フィールドを持ち、テンプレートがそのまま描画する。

meta レンダリングには利用者の `reports.yaml` が無いので、分割は **固定の内部 file_per**（`meta_templates.META_REPORTS_CONFIG` = `__entity_defs.item` / `__entity_data.item` / `__queries.item`）で駆動する。各結果アイテムの anchor_path `/{view}/{id}` から通常の page_path 規則で `{view}/{id}.md` が導かれる — **1 ノード 1 ページ**。共有コンテキストである data root と schema は、子テンプレが anchor_path で直接引く（root = `node("/")`、schema = `node("/__definition/entities")`。`node` は anchor_path→node 解決の global で、`build_node_map` が全 wrap ノードを anchor_path で索けるようにするため成り立つ）ので、主題ノードは identity フィールドだけを持てばよい。

> **背景: 別ページが要るならノードを一つ立てる.** 旧実装は `__root.md` 内で合成 dict（アンカーパス無し）を組み、予約キー `_split` ＋ template-keyed fallback（`{template_stem}/{id}.md`）で分割していた。これは「1 ノード→複数ページ」を fallback がテンプレート名で曖昧性を割る誤魔化しで、**one-node-one-page ポリシー違反**だった。別ページが要るならノードを一つ立てる — 同一 entity に 2 ページ要るなら `__entity_defs` と `__entity_data` の 2 ノードを立てる、というのがこの原則の実践で、`_split` マーカーと fallback は撤去された。

> **残: 出力ディレクトリの集約（F9）.** これら `__{view}/` は今も output 直下に横並びで散る。単一ディレクトリ配下への集約は F9 が担う。

## Proposals

> 残タスク（Phase 11/13）: 複数プロファイル (C5/C6)、meta 出力ディレクトリの集約 (F9)。

### 複数プロファイル

複数バリエーション（Web 版と PDF 版を並行配信する等）を 1 プロジェクトから出すために、`profiles:` キーで列挙する形を追加する:

```yaml
# definition/reports.yaml — 複数プロファイル
profiles:
  web:
    file_per:
      - erds.item
      - erds.item.entities.item
  pdf:
    file_per: []              # 分割なし → 全部 index.md にインライン
```

**トップ直書きの形と `profiles:` だけがある形の二択**。両方を混在させる（トップに共通設定を書きつつ `profiles:` でも書く）形は不可とする。

出力ディレクトリは `profiles:` の有無で変わる:

- トップ直書き form（`profiles:` キー無し）→ `{outDir}/reports/{page_path}`（フラット）
- `profiles:` あり → `{outDir}/reports/{profile_name}/{page_path}`（プロファイル軸が一段挟まる）

`{outDir}` 直下の診断系出力はプロファイル横断で常に同じ位置に出る。プロファイル概念は **レポートの中** にのみ存在する。
