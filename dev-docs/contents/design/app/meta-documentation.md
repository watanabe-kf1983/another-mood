# メタドキュメンテーション

ユーザが書いたスキーマ定義とクエリ定義を、ツールが内蔵のテンプレートで自動的に可視化する機能。

## External Design

### Entity と Query のページ構成 (非対称)

Entity と Query でページ分け方が異なる:

| 種別 | ページ構成 |
|---|---|
| Entity | `__meta_entity` (Schema) と `__table_view` (Data) の **2 ページ**、相互リンクで往復 |
| Query | `__meta_query` に Definition / Shape / Results の **3 セクション 1 ページ** |

#### 背景: なぜ非対称か

**artifact の結合度**で決めている。

**Entity** は Schema と Data が独立した user source:

- Schema: user が JSON Schema として authoring した定義
- Data: user が YAML として authoring したレコード
- どちらも単独で意味を持つ (「このフィールドは何?」 vs 「このレコードは?」)
- → **分離 2 ページ**、それぞれ別の読者の問いに答える

**Query** は Definition / Shape / Results が 1 つの recipe 由来の束:

- Definition: user が書いた DSL
- Shape: Definition から deterministic に推論 (`apply_to_catalog`)
- Results: Definition + 上流データから生成
- どれも単独では不完全: Definition は抽象 recipe、Shape は「結果の形」単独で
  意味が薄く、Results は Definition 無しに「何のクエリか」分からない
- → **統合 1 ページ**、3 者がセットで初めて意味を成す

Entity の Data を見て味見して Schema を直すことは普通はないが、Query の Results
を味見して DSL (Recipe) を修正するのは日常。Author の feedback loop が
そのまま結合度の差を裏付けている。

#### 業界ツールとの対応

- **DBeaver / Snowsight / MS Access のテーブルブラウザ**: Schema (DDL / Properties)
  と Data (Datasheet) は別タブ — 本ツールの Entity 2 ページに対応
- **SQL エディタ + Results pane** (DBeaver の SQL Editor, Snowsight の worksheet):
  Query と Results は同ウィンドウ上下 — 本ツールの Query 1 ページに対応

この非対称は artifact 結合度の差を反映しており、業界慣例とも整合する。

### Query View の Shape が必須な理由

本ツールは複合型 (object / object[]) を許容するため、カラムヘッダと
サンプル行だけでは結果形状が伝わらない (`tasks` カラムが scalar 文字列なのか、
`categories.tasks` 型の配列なのかが値だけでは断定できない)。

Shape セクションで各出力フィールドの型 + entity ref を明示する
ことで、template 著者 / MCP 経由の LLM / 人間の読者すべてに対して型情報が
programmatic に伝わる。SQL クライアントが (全カラムスカラ前提で) 型表示を
省略できるのと対照的。

Shape は Query Object の `apply_to_catalog` が生成する。

### ER 図シリーズ

メタドキュメンテーションには 3 つの Mermaid classDiagram が登場する:

- `__root` 全体図 (F4a) — カタログ全体の関係を俯瞰
- `__meta_entity/<id>.md` 近傍図 (F4b) — focus entity の周辺
- `__meta_query/<id>.md` Source Diagram (F4c) — クエリのソース entity 群

3 図の variation:

| 観点 | `__root` 全体図 (F4a) | `__meta_entity` 近傍図 (F4b) | `__meta_query` Source Diagram (F4c) |
|---|---|---|---|
| node 集合 | user 領域 + `prose` 全体 | focus + descendants + focus subtree からの FK out 先 | `query.from` ∪ `query.join[].to` (top-level entity に閉じる) |
| 属性表示 | 全 node ヘッダのみ | focus + descendants は全属性、FK out 先はヘッダのみ | 全 node ヘッダのみ |
| composition edge | 全 node 間の親子 | 描画範囲内に両端がある親子のみ | 両端が nodes 内 (top-level 同士は実質発火しないが規則を揃える) |
| association edge | 両端が node 集合に入る FK | focus subtree → FK out 先のみ (FK in は描かない) | 各 top-level node の subtree-aggregated FK で target も nodes 内 |

下記の設計判断は 3 図に共通する。各図に特有の判断は各節に書く。

#### 背景: なぜ classDiagram か (erDiagram でなく)

1. **視覚密度** — `erDiagram` はヘッダ帯付きの分厚いボックスで縦に伸びる。多 entity を一画面に収めにくい。`classDiagram` の方がスキーマ可視化として読める密度になる。
2. **意味的に分けて描ける** — このツールのカタログには 2 種類の関係がある:
    - **composition**: `Entity.parent_entity` 連鎖 (singleton-flatten によるネスト分解)。`*--` で描く
    - **association**: `Attribute.x_ref` による FK。`-->` で描く

   `classDiagram` は UML 表記でこの 2 つを区別できる。`erDiagram` だとどちらも「リレーション」に潰れて情報量が落ちる。

ユーザ向けの呼称は「ER 図」のまま使う (読者の探し方は "ER 図" / "schema diagram" であり、内部構文は実装詳細)。

#### 背景: クラス名は Entity id ではなく ObjectType id を使う

各クラスのラベル (および sanitize した alias) は **entity.id ではなく `entity.item_type.id` (= ObjectType id)** から組む。例: entity `artists` → class `artists.item`、descendant entity `artists.members` → class `artists.item.members.item`。

理由は UML / ER 用語との整合。UML の class 名は型 (= 1 件分のもの) を指すので単数形が原則であり、本ツールの 2 階層 (Entity = collection identity 複数形 / ObjectType = item identity `.item` 付き) のうち ObjectType 側がそれにあたる。`__meta_entity/<id>.md` ページが既に `## Type: artists.item` を見出しに出しているのと表記が揃う。

### `__root` の Entity Relationship 図

トップページ (`__root`) に「全 entity の関係を俯瞰する」図を出す。ノード集合は user 領域 + `prose` (descendant 含む)、composition は親子、association は両端がノード集合に入る FK のみ。各クラスはヘッダのみ (属性内訳は `__meta_entity` 側の表が担う)。

### `__meta_entity/<id>.md` の近傍 ER 図

各 entity ページの先頭 (タイトル直下、`[→ Entity Data]` リンクの直下) に、focus entity + その descendants + focus subtree が FK 参照する先だけを描く小さな classDiagram を出す。各 variation は ER 図シリーズ節の表を参照。

#### 背景: attribute 表との重複は許容

主役 entity の属性は近傍図にも attributes 表にも出るが、両方とも保持する:

- ER 図: 関係を含めた構造の **視覚的概観** (属性の型は補助情報)
- attributes 表: `references` 列の隣接 entity ページへのリンク、`validation` / `metadata` 等の **詳細参照** (ER 図に載らない情報を持つ)

役割が分かれており、片方を削ると失われる読者の問いがある。S1 / showcase/music の実機検証でも視覚的にうるさく感じなかったため、いったん両方を残す。

### `__meta_query/<id>.md` の Source Diagram

各 query ページの先頭 (タイトル直下、`## Definition` の直前) に、クエリのソース entity 群とその関係を示す classDiagram を出す。MS Access のクエリデザインビュー上部に並ぶ「テーブルとそれを結ぶ関係線」に相当するビュー。各 variation は ER 図シリーズ節の表を参照。

#### 背景: association edge は subtree-aggregated

各 top-level node の subtree (self + descendants) を walk して x_ref attribute を集約し、target が nodes 内なら top → target の edge として描く。edge ラベルは top からの相対 path (例: descendant `テーブル.列` の `型` 属性なら `列.型`、ネスト属性 `列.参照.テーブル` ならそのまま `列.参照.テーブル`)。

理由は MS Access designer 流の「クエリの入り口テーブル同士が *どのように関係しているか* を視覚化する」用途を満たすため。本ツールは複合型を許容するため、テーブル ←→ テーブル の関係は親 top-level の直接属性ではなく descendant の attribute に乗ることが多い (例: `テーブル.列.型 → 型対応`)。これを strict に「直接属性のみ」と読むと、JOIN の `on` で実際に使われている関係が図上で消える。aggregation で top-level に持ち上げることで、designer view の意図 (= 関係をテーブル間の線として見せる) と Proposal の文言 (= 関係をテーブル間の edge として描く) の両方を満たせる。

#### 背景: 属性表示はヘッダのみ

per-query 図の目的は「このクエリがどのソースを束ねているか」を一望することで、各 entity の中身は `## Shape` 節 (= apply_to_catalog による出力形状) や `__meta_entity/<id>.md` (= 各 entity の定義ページ) 側が担う。属性行を載せるとノード数 × 属性数で図が縦長になり、Source Diagram の "querydesigner-like overview" としての密度感が崩れる。

## Internal Design

### Entity と ObjectType

データカタログのエントリは 2 階層で表現される:

- **Entity**: データツリー上の到達経路を表す identifier `id` (例: `categories.tasks`)。クエリ DSL の `from:`、paging 設定、表示見出しに使う（アンカーパスは別概念、[anchor-spec.md](../generator/anchor-spec.md) 参照）
- **ObjectType**: Entity の中の 1 つの item の型 `id` (例: `categories.item.tasks.item`)。コレクションを 1 段降りるごとに `.item` を付加。FK 参照や型レベルの cross-reference に使う

Entity は自身の `item_type` フィールドを通じて ObjectType を保持する。

詳細は [schema-spec.md](../normalizer/schema-spec.md)「Entity 名」節を参照。

### 自己記述カタログ (`__definition.*`)

データカタログ自体を `__definition.entities` / `__definition.queries` という built-in entity として登録し、クエリ DSL から `from: __definition.*` で walk 可能にしている。built-in メタドキュメンテーションテンプレートが自分のメタデータを自分の DSL から読めるようにするための足場。

各 catalog dataclass (`Entity` / `Attribute` / `Query` / `SelectItem`) が自身の `catalog()` classmethod で構造を Node 形式で返し、呼び出し側 (`inspect_schema._emit_definition_catalog`) が `to_flat(root_name)` で id を割り当てて `builtin=True` を付与し、`out_dir/__builtin/__definition.yaml` に書き出す。データクラス自身は namespace 内の自分の位置を知らない。

`__definition` 自身はカタログに entity として含まれない。ユーザ領域のスキーマルートと同じ扱いで、トップレベル singleton は entity として現れず、その直下の `__definition.entities` / `__definition.queries` が dotted id を持つ top-level entity (`parent_entity=null`) として並ぶ。

`composer` 側の `sources` は 3 上流出力 (normalize_contents, inspect_schema, derive_queries) の deep-merge で組まれており、`__definition.entities` レコードはスキーマ宣言として上流ステージで使われると同時に、ここでは `From.apply` の walk 対象としても機能する (= データ / スキーマの双役)。

### メタドキュメンテーションの DSL 化境界

built-in メタドキュメンテーション (`__meta_entity` / `__table_view` / `__meta_query` の各ページ) では、tabular な leaf 操作のみを Query DSL に持ち出す (各ページの主題ノードを生む同名クエリと、一覧用の `__user_entity_roots` / `__user_queries` 等がそれ)。entity ツリーの descent (`entity.id.startswith(...)` による子孫マッチ、`walk_entity` フィルタによる view データの `parent_entity` 連鎖 descent) は Jinja2 / Python ヘルパに残す住み分けにしている。

#### 背景

メタカタログは `parent_entity` リンクのツリーで、relational/tabular な DSL とは噛み合わない。ツリー descent を DSL で表現するには SQL の `WITH RECURSIVE` や Cypher のパス構文相当 (推移閉包 / 非 equi join) が要り、YAML DSL に押し込むと確実に式言語的な異物になる。

leaf データの集計・整形は DSL の母語、tree descent は Python (Jinja2 フィルタ) の母語、という住み分けに留めるのが、DSL の単純さとテンプレートの可読性の両方に効く。

