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

### `__root` の Entity Relationship 図

トップページ (`__root`) に「全 entity の関係を俯瞰する」Mermaid 図 (classDiagram) を出す。ノード集合は user 領域 + `prose` (descendant 含む)、composition は親子、association は両端がノード集合に入る FK のみ。edge ラベルは FK 属性名、カーディナリティ表記なし、各クラスはヘッダのみ (属性内訳は `__meta_entity` 側の表が担う)。

#### 背景: クラス名は Entity id ではなく ObjectType id を使う

各クラスのラベル (および sanitize した alias) は **entity.id ではなく `entity.item_type.id` (= ObjectType id)** から組む。例: entity `artists` → class `artists.item`、descendant entity `artists.members` → class `artists.item.members.item`。

理由は UML / ER 用語との整合。UML の class 名は型 (= 1 件分のもの) を指すので単数形が原則であり、本ツールの 2 階層 (Entity = collection identity 複数形 / ObjectType = item identity `.item` 付き) のうち ObjectType 側がそれにあたる。`__meta_entity/<id>.md` ページが既に `## Type: artists.item` を見出しに出しているのと表記が揃う。

副作用として composition edge (`artists.item *-- artists.item.members.item`) が `.item` チェーンで親子の埋め込み path をそのまま見せる形になる。冗長ではあるが composition の意味を裏付ける情報量として機能する。ユーザが Entity 名 (複数形) でしか考えない場合のスムーズさは多少落ちるが、UML/ER 慣例側に振った。

#### 背景: なぜ classDiagram か (erDiagram でなく)

#### 背景: なぜ classDiagram か (erDiagram でなく)

1. **視覚密度** — `erDiagram` はヘッダ帯付きの分厚いボックスで縦に伸びる。多 entity を一画面に収めにくい。`classDiagram` の方がスキーマ可視化として読める密度になる。
2. **意味的に分けて描ける** — このツールのカタログには 2 種類の関係がある:
    - **composition**: `Entity.parent_entity` 連鎖 (singleton-flatten によるネスト分解)。`*--` で描く
    - **association**: `Attribute.x_ref` による FK。`-->` で描く

   `classDiagram` は UML 表記でこの 2 つを区別できる。`erDiagram` だとどちらも「リレーション」に潰れて情報量が落ちる。

ユーザ向けの呼称は「ER 図」のまま使う (読者の探し方は "ER 図" / "schema diagram" であり、内部構文は実装詳細)。

#### 背景: カーディナリティを書かない

矢印根元 (source 側) と矢の先 (target 側) のカーディナリティ表記は、初期版では両端とも書かない。

- **source 側は常に `0..*`** — D8/D9 (unique 制約) が入るまで「source レコードが target をシェアしない」保証ができないので、機械的に常に `0..*`。常に同じ値だと情報量ゼロ。
- **target 側は `1` or `0..1`** — `attribute.required` で決まる。情報を持つが、per-entity 図では attributes 表の `required` 列と重複する。
- **clutter コスト** — 多 FK の entity で `0..* --- 1` が並ぶと視覚的に重い。

D8/D9 で unique 制約が入った段階で初めて source 側が `0..*` / `0..1` / `1..1` に分かれるため、その時に source 側だけ追加するのが筋がいい。

#### 背景: edge ラベルに attribute 名を載せる

association edge には FK 属性名をラベルとして載せる。カーディナリティより実用情報量が高い:

- どの FK か一目で分かる
- 同じ pair 間に複数 FK があるケース (将来 `composer_id` / `lyricist_id` が両方 `artists` を指す等) で必須

composition edge はラベル無し (親子関係は自明)。

#### 背景: dotted catalog id の alias 化

ObjectType id は `.item` で必ずドット入り (`artists.item`、descendant では `artists.item.members.item`)。Mermaid classDiagram の class 名はドットを namespace 区切りとして特別扱いするため、そのままでは class 名に使えない。`mermaid_class_id` フィルタで `.` を `_` に置換し、ラベル付き class 表記 (`class artists_item["artists.item"]`) で alias と表示名を両立させる。

ユーザ-land 領域では id 空間にドットが入らない想定なので、user-land のテンプレートでは alias 化フィルタは不要 (S1 = `showcase/japanese-table-design` で確認済み)。

#### 背景: user-land 先行 / built-in 輸入 (S1 → F4)

ER 図は本ツールの「ユーザ向けの中核ユースケース」(ソフトウェアシステム設計書のテーブル定義から自動的に ERD を描く) でもあるため、built-in メタドキュメンテーションで先に走らせるのではなく user-land で同じことが成立するか ([S1](system-dev-docs.md#s1-テーブル定義--2-種類のスキーマ図-showcasejapanese-table-design)) を先に確認した。built-in 先行だと (a) user-land で再現できない可能性が surface しない、(b) ツール価値提案の検証が遅れる、(c) Unicode / 識別子問題が後出しになる (built-in は catalog id (ASCII) しか扱わないため、日本語識別子下での Mermaid quoting 制約が surface しない)。

S1 完了時点での実機検証結果 (Mermaid Unicode 制約、不足プリミティブの有無、SQL 型と classDiagram の衝突) は [system-dev-docs.md](system-dev-docs.md#s1-テーブル定義--2-種類のスキーマ図-showcasejapanese-table-design) に集約。F4 はその結論を前提に進めている (catalog 型は括弧無しの論理型なので classDiagram の attribute 表記と衝突しない)。

## Internal Design

### Entity と ObjectType

データカタログのエントリは 2 階層で表現される:

- **Entity**: データツリー上の到達経路を表す identifier `id` (例: `categories.tasks`)。クエリ DSL の `from:`、URL/anchor、ファイルパス、表示見出しに使う
- **ObjectType**: Entity の中の 1 つの item の型 `id` (例: `categories.item.tasks.item`)。コレクションを 1 段降りるごとに `.item` を付加。FK 参照や型レベルの cross-reference に使う

Entity は自身の `item_type` フィールドを通じて ObjectType を保持する。

詳細は [schema-spec.md](../normalizer/schema-spec.md)「Entity 名」節を参照。

### 自己記述カタログ (`__definition.*`)

データカタログ自体を `__definition.entities` / `__definition.queries` という built-in entity として登録し、クエリ DSL から `from: __definition.*` で walk 可能にしている。built-in メタドキュメンテーションテンプレートが自分のメタデータを自分の DSL から読めるようにするための足場。

各 catalog dataclass (`Entity` / `Attribute` / `Query` / `SelectItem`) が自身の `catalog()` classmethod で構造を Node 形式で返し、呼び出し側 (`inspect_schema._emit_definition_catalog`) が `to_flat(root_name)` で id を割り当てて `builtin=True` を付与し、`out_dir/__builtin/__definition.yaml` に書き出す。データクラス自身は namespace 内の自分の位置を知らない。

`__definition` 自身はカタログに entity として含まれない。ユーザ領域のスキーマルートと同じ扱いで、トップレベル singleton は entity として現れず、その直下の `__definition.entities` / `__definition.queries` が dotted id を持つ top-level entity (`parent_entity=null`) として並ぶ。

`composer` 側の `sources` は 3 上流出力 (normalize_contents, inspect_schema, derive_queries) の deep-merge で組まれており、`__definition.entities` レコードはスキーマ宣言として上流ステージで使われると同時に、ここでは `From.apply` の walk 対象としても機能する (= データ / スキーマの双役)。

### メタドキュメンテーションの DSL 化境界

built-in メタドキュメンテーション (`__meta_entity` / `__table_view` / `__meta_query`) では、tabular な leaf 操作のみを Query DSL に持ち出し (`__entity_roots` / `__user_entity_roots` / `__user_queries` がそれ)、entity ツリーの descent (`entity.id.startswith(...)` による子孫マッチ、`walk_entity` フィルタによる view データの `parent_entity` 連鎖 descent) は Jinja2 / Python ヘルパに残す住み分けにしている。

#### 背景

メタカタログは `parent_entity` リンクのツリーで、relational/tabular な DSL とは噛み合わない。ツリー descent を DSL で表現するには SQL の `WITH RECURSIVE` や Cypher のパス構文相当 (推移閉包 / 非 equi join) が要り、YAML DSL に押し込むと確実に式言語的な異物になる。

leaf データの集計・整形は DSL の母語、tree descent は Python (Jinja2 フィルタ) の母語、という住み分けに留めるのが、DSL の単純さとテンプレートの可読性の両方に効く。

## Proposals

### ER 図の追加配置 (F4b / F4c)

F4a で `__root` 全体図を入れたあとに、近傍図と per-query 図を別配置として段階投入する。基盤 (Mermaid classDiagram 採用、composition/association 区別、`__user_content_entities` クエリ、`mermaid_class_id` フィルタ、edge ラベル/カーディナリティ規約) は F4a で確立しており、External Design の「`__root` の Entity Relationship 図」節を参照。

| 配置 | nodes | composition edge | association edge | 属性 |
|---|---|---|---|---|
| **近傍図** (`__meta_entity/<id>.md`、F4b) | focus + focus の descendants + focus subtree の FK out 先 | 描画範囲内の親子 | focus subtree から FK out 先への矢印のみ (FK in は描かない) | focus + descendants は全属性、FK out 先はヘッダのみ |
| **per-query 図** (`__meta_query/<id>.md`、F4c) | `{query.from} ∪ {j.to for j in query.join}` (= top-level entity の集合) | nodes 内に親子があれば描く | nodes 内に両端がある FK | なし (ヘッダのみ) |

#### 近傍図 (F4b) の attribute 表との重複

主役 entity の attributes は `__meta_entity` ページに既に表として出ている。近傍図でも主役を全属性表示するため、同じ情報が二重に出る形になる。**いったんそのまま実装して、実物を見て鬱陶しければ削る**。

#### per-query 図 (F4c) のノード集合が top-level に閉じる理由

`From.derive` は `catalog.has_child(name)` で top-level entity のみを引く。`build_tree` は `parent_entity is None` のものしか virtual root の子にしないため、`from: artists.members` のような descendant 直接指定はそもそも build エラーになる。`Join.from_dict` も内部で `From(name=to)` を作って root_catalog 上で derive するので同じ制約に従う。

このため per-query 図のノード集合は `query.from` と `query.join[].to` を素直に union するだけで top-level entity の集合になる。MS Access のクエリデザインビューと同じく「クエリの入り口テーブル群とその間の関係だけ」を示す形に自然に収まる。

#### 近傍図のフィルタ式パターン

tree descent は flat catalog に対する filter で十分書ける (再帰不要)。`entity.id == focus_id or entity.id.startswith(focus_id ~ ".")` で focus + descendants を抽出するパターンは `__meta_entity.md` / `__table_view.md` に既出。per-query 図は `query.from` と `query.join[].to` から id 集合を組み、`__user_content_entities` を引き当てる。
