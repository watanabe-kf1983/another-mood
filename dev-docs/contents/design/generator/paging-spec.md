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

### 分割ルール

`{% mood_view "tpl" with NODE %}` は主題ノードの `_meta.object_type_id`（[generator.md](generator.md#ノードメタデータ)）を `file_per` と照合して振る舞いを決める:

- **`file_per` の分割単位に含まれる** → 別ページに書き出し、**呼び出し位置には何も残さない**（`render_to_file` して空文字列を返す）
- **含まれない** → その場にインライン展開（`{% include %}` 相当）

親ページ側に出すリンクや目次は **mood_view が自動生成しない**。author が `| link`（[B4](../../../tasks.md)）で別途書く。`| link` は target の page_path（[B6](generator.md#ページパスの導出-b6)）で解決されるので、**分割なら別ページ URL・インラインなら同ページ内 `#fragment`** に自動で適応する。これにより author は分割/インラインを意識せず、同じテンプレートが Web 用（分割）でも PDF 用（全インライン）でも動く。

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

> **背景: なぜ自動リンクを mood_view に持たせないか.** 当初案は「分割時に親へリンクを残す」だったが、リンク解決の責務は既に `| link`（B4）＋ page_path（B6）にあり、しかも分割/インラインへ自動適応する。mood_view にリンク生成を畳み込むと二重実装になり、かつ親側の周辺マークアップ（リスト記号・付随情報）を author が制御できなくなる。mood_view の責務は「このノードの内容をどこに置くか」の一点に保つ。`{% mood_view %}` にブロック本体やアーム（`{% split %}` 等の発明語）を持たせる糖衣も検討したが、two-loop パターンが既知の素の構文だけで同じことを達成するため採らない。

> **注: インライン展開時の fragment 着地は未完（C9）.** `| link` のインライン解決は `#anchor_path` を指すが、受け側 `<a id>` の発行は未実装（[anchor-spec.md のアンカー発行フィルタ](anchor-spec.md#アンカー発行フィルタ-b9--c9)、B9→C9）。two-loop の PDF 体験（同ページ内ジャンプ）が完成するのは C9 まで行ってから。分割側のページ単位リンクは path 部で機能する。

> **背景: per-call-site インライン上書きは持たない（C8 で `inline` キーワードを廃止）.** 旧 `{% mood_view ... inline %}` は file_per 機構導入前の唯一のインライン手段だったが、file_per 導入後はインライン意図を **型単位ポリシー（file_per から外す）**で表現でき、call-site 上書きとの併存は footgun を生んだ: file_per 対象の型を call-site で `inline` 強制すると、そのノードが「自前ページ」と「インライン本文」に**二重出力**され、`| link` の指す先と内容の所在がずれる。よってインラインは型単位の一手段に統一した。将来 per-instance 需要が出たら別機構で入れ直す。

### ページパスと出力ディレクトリ

ページパスはアンカーパスから直接導出される（B6）。導出規則は `ReportsConfig.page_path` が持ち、その定義は [generator.md](generator.md#ページパスの導出-b6) を正本とする。anchor_path を流用するため、セグメントの**エスケープも anchor_path と同じ IRI 形を継承する**（[anchor-spec.md](anchor-spec.md#escape-規則) — 非 ASCII の `ucschar` は生のまま、`/` 等の構造文字と FS 危険文字は percent-encode）。要点:

- **非 root**: anchor_path の先頭 `/` を落として `.md` を付けたもの（例: `/erds/user-management` → `erds/user-management.md`、`/erds/user-management/entities/user` → `erds/user-management/entities/user.md`、シングルトン `/overview` → `overview.md`）
- **root (`anchor_path == "/"`)**: `index.md` 固定（file_per 不問）

これによりアンカーパス規則と paging path 規則が同じ shape で表現される。

`page_path` は **レポートルート相対**。実ファイルの書き出し位置は mood_view が出力ディレクトリ規約のマウント先（`{outDir}/reports/`）を被せて決める（`{outDir}/reports/{page_path}`）。`{outDir}` 直下の診断系出力（`index.md`、`__meta_entity/` 等）はマウント先と無関係に常に同じ位置に出る。

> 複数プロファイル（[Proposals](#複数プロファイル)）を入れると、`reports/` の下に `{profile_name}` 軸が一段挟まる（`{outDir}/reports/{profile_name}/{page_path}`）。

## Internal Design

### meta 診断の分割 — マーカー方式

`{% mood_view %}` の分割/インライン判定は **主題が実ツリーノードか否か**で二段になる:

- **実ノード**（`MappingNode` / `ArrayNode`）→ [分割ルール](#分割ルール) の file_per 判定
- **非ノード（合成 dict）→ 既定はインライン。予約キー `_split` を持つときだけ分割**（template-keyed fallback パス `{template_stem}/{id}.md`）

> **背景: なぜ常時分割でなくマーカーか.** 素直なルールでは「file_per に載らない非ノードはインライン」が自然（合成 dict は `object_type_id` を持たず file_per に載りようがない）。当初実装は非ノードを一律分割していたが、それは meta 診断を通すためだけの不自然な既定で、読み手に「なぜこの非ノードが分割されるのか」が伝わらない。`_split` を meta テンプレ側に明示させることで既定を自然な「インライン」に戻し、過渡的な負債を **マーカーを立てた箇所＝負債** として可視化する。

`_split` は meta 診断テンプレート（`__meta_entity` / `__table_view` / `__meta_query`）専用の暫定オプトイン。これらは `__root.md` 内で組む合成 dict（アンカーパスを持たない）を主題に、**同一 entity を複数テンプレートで複数ページ**（`__meta_entity/{id}.md` と `__table_view/{id}.md`）へ出すため `_split` を立てている。1 ノードは anchor_path も page_path も 1 つなので、これは **one-node-one-page ポリシー違反**であり、fallback がテンプレート名をパスに焼いて曖昧性を割っている。

> **位置づけ: これは確定した負債.** 別ページが要るならクエリを一本増やすのが本ツールの筋であり、「1 ノード→複数ページ」は畳むべき誤魔化し。解消は同一 meta クラスタの **F9（meta 出力を単一ディレクトリへ集約・所有）→ E12（各ビューを別クエリで実ノード化し page_path 一本に）** で行う。E12 で合成 dict が実ノードになれば `_split` マーカーは不要になり撤去する。詳細は [meta 子テンプレートへの root threading 解消](#meta-子テンプレートへの-root-threading-解消e12) を参照。

## Proposals

> 残タスク（Phase 11/13）: 複数プロファイル (C5/C6)、アンカー発行 (B9→C9、[anchor-spec.md](anchor-spec.md#アンカー発行フィルタ-b9--c9))、meta 診断負債の解消 (E12/F9)、prose body フィルタ (B5)。

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

### meta 子テンプレートへの root threading 解消（E12）

> [テンプレート主題のノード受け取りと `this` 束縛](#テンプレート主題のノード受け取りと-this-束縛)・出力パス統一（C3）は実装済み。残るのは B5 簡約・meta 子テンプレートへの root threading 解消（E12）。

`this` 束縛で主題がノードになったことを足場に、まだ残る簡約がある:

1. **B4/B5 の source-node プラミング簡約.** リンク解決の「いま自分はどのページか（source node）」を `this` から取れるので、[generator.md](generator.md#リンク解決-b4-b5) が想定する **per-render の resolver closure-binding（source node 束縛）が不要**になり、resolver は静的な `(ReportsConfig, node_map)` だけ束縛すればよくなる（B4 実装済み、B5 実装時に取り込む）。

2. **meta 子テンプレートへの root threading 解消.** meta 子テンプレート（`__table_view` / `__meta_query`）は `walk_entity` の入力に root の全ビュー集合を要するが、主題が合成 dict（非ツリーノード）で親チェーンを持たないため、`__root.md` が root ノードを `root` キーで明示的に渡している。**E12（meta 診断データを query で実ノード化）**で子が実ノードになれば、親チェーン経由で root に届き、この threading は不要になる（同時に [`_split` マーカー](#meta-診断の分割--マーカー方式)も撤去される）。
