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

### ER 図 (F4a-F4c)

Phase 10 タスク [F4a](../../../tasks.md) / [F4b](../../../tasks.md) / [F4c](../../../tasks.md)。前提 D, E11, E3。3 配置 × インクリメンタル投入。

#### 描画記法: classDiagram (ER 図でなく)

Mermaid `erDiagram` ではなく `classDiagram` 構文で描く。「ER 図」というユーザ向けの呼称はそのまま使う (読者の探し方は "ER 図" / "schema diagram" であり、内部構文は実装詳細)。

##### 背景: なぜ classDiagram か

理由は 2 つ:

1. **視覚密度** — `erDiagram` はヘッダ帯付きの分厚いボックスで縦に伸びる。多 entity を一画面に収めにくい。`classDiagram` の方がスキーマ可視化として読める密度になる。
2. **意味的に分けて描ける** — このツールのカタログには 2 種類の関係がある:
    - **composition**: `Entity.parent_entity` 連鎖 (singleton-flatten によるネスト分解)。`*--` で描く
    - **association**: `Attribute.x_ref` による FK。`-->` で描く

   `classDiagram` は UML 表記でこの 2 つを区別できる。`erDiagram` だとどちらも「リレーション」に潰れて情報量が落ちる。例: music の `artists *-- artists.members` (オーナーシップ) と `albums --> artists` (参照) は明確に別概念。

#### 配置とスコープ

3 ヶ所に描く。各々の役割と描画ルール:

| 配置 | nodes | composition edge | association edge | 属性 |
|---|---|---|---|---|
| **全体図** (`index.md`) | `__user_content_entities` 全件 (user 領域 + prose、descendant 含む) | 描画範囲内の親子全部 | 描画範囲内に両端がある FK 全部 | なし (ヘッダのみ) |
| **近傍図** (`__meta_entity/<id>.md`) | focus + focus の descendants + focus subtree の FK out 先 | 描画範囲内の親子 | focus subtree から FK out 先への矢印のみ (FK in は描かない) | focus + descendants は全属性、FK out 先はヘッダのみ |
| **per-query 図** (`__meta_query/<id>.md`) | `{query.from} ∪ {j.to for j in query.join}` (= top-level entity の集合) | nodes 内に親子があれば描く | nodes 内に両端がある FK | なし (ヘッダのみ) |

共通ルール:

- **`view: true` の entity は描かない** — クエリ由来の派生 view は schema として描く対象外
- **edge ラベル**: composition は無し (親子関係は自明)、association は **FK 属性名** (`artist_id` 等)
- **カーディナリティは書かない** — 詳細は下記「カーディナリティを書かない理由」
- **escape は最小対応**: 最初は dotted entity id の classDiagram alias 化 (`mermaid_class_id` フィルタ) のみ。他のエスケープは実害が出てから対応

##### per-query 図のノード集合が top-level に閉じる理由

`From.derive` は `catalog.has_child(name)` で top-level entity のみを引く。`build_tree` は `parent_entity is None` のものしか virtual root の子にしないため、`from: artists.members` のような descendant 直接指定はそもそも build エラーになる。`Join.from_dict` も内部で `From(name=to)` を作って root_catalog 上で derive するので同じ制約に従う。

このため per-query 図のノード集合は `query.from` (string) と `query.join[].to` (string) を素直に union するだけで top-level entity の集合になり、ancestor chain を描き足すかどうかの判断は不要。MS Access のクエリデザインビューと同じく「クエリの入り口テーブル群とその間の関係だけ」を示す形に自然に収まる。

##### 近傍図の attribute 表との重複

主役 entity の attributes は `__meta_entity` ページに既に表として出ている。近傍図でも主役を全属性表示するため、同じ情報が二重に出る形になる。**いったんそのまま実装して、実物を見て鬱陶しければ削る**。

#### 描画判断の根拠

##### カーディナリティを書かない理由

矢印根元 (source 側) と矢の先 (target 側) のカーディナリティ表記は、初期版では **両端とも書かない**。

- **source 側は常に `0..*`** — D8/D9 (unique 制約) が入るまで「source レコードが target をシェアしない」保証ができないので、機械的に常に `0..*`。常に同じ値だと情報量ゼロ。
- **target 側は `1` or `0..1`** — `attribute.required` で決まる。情報を持つが、per-entity 図では attributes 表の `required` 列と重複する。全体図 / per-query 図でもリーダーが「nullable な FK か」を真剣に知りたい場面は稀で、必要なら entity 詳細ページに飛べばよい。
- **clutter コスト** — 多 FK の entity (e.g. music の `albums` は 3 FK) で `0..* --- 1` が並ぶと視覚的に重い。

D8/D9 で unique 制約が入った段階で、初めて source 側が `0..*` / `0..1` / `1..1` に分かれるため、その時に source 側だけ追加するのが筋がいい。要望が surface したら検討。

##### edge ラベルに attribute 名を載せる

association edge には **FK 属性名** をラベルとして載せる:

```
albums --> artists : artist_id
albums --> labels : label_id
albums --> genres : genre_id
```

カーディナリティより実用情報量が高い:

- どの FK か一目で分かる
- 同じ pair 間に複数 FK があるケース (将来 `composer_id` / `lyricist_id` が両方 `artists` を指す等) で必須

composition edge はラベル無し (親子関係は自明)。

#### Internal Design ドラフト

##### 新規組み込みクエリ: `__user_content_entities`

全体図および per-query 図のノード候補集合。`__user_entity_roots` から `parent_entity: { exists: false }` 条件を外したバージョン。descendant も含む:

```yaml
__user_content_entities:
  from: __definition.entities
  where:
    view: false
    not:
      id: { startswith: __ }
  select:
    - item: id
    - item: parent_entity
    - item: builtin
    - item: item_type
```

注: `view: false` で query 由来の派生 entity が落ちる。`id: { startswith: __ }` の否定で `__definition.*` などの catalog-internal entity が落ちる。`prose` は `builtin: true` だが id に `__` プレフィクスが無いので含まれる。

##### Jinja2 フィルタ追加: `mermaid_class_id`

dotted entity id を classDiagram 安全な class 識別子に変換:

```python
def _mermaid_class_id(entity_id: str) -> str:
    return entity_id.replace(".", "__")
```

`artists.members` → `artists__members`。classDiagram の class 名はドット非対応のため必須。`__meta_entity/<id>.md` 等の他フィルタと同じく `_FILTERS` テーブルに登録する。

他のエスケープ (引用符、改行、`<>` 等) は description / metadata を図に出さない方針なので初期版では不要。実害が surface したら対応。

##### テンプレート内のフィルタ式パターン

tree descent は flat catalog に対する filter で十分書ける (再帰不要)。全体図の骨格:

```jinja2
```mermaid
classDiagram
{# nodes #}
{% for entity in __user_content_entities -%}
class {{ entity.id | mermaid_class_id }}["{{ entity.id }}"]
{% endfor -%}
{# composition edges #}
{% for entity in __user_content_entities if entity.parent_entity -%}
{{ entity.parent_entity | mermaid_class_id }} *-- {{ entity.id | mermaid_class_id }}
{% endfor -%}
{# association edges #}
{% set node_ids = __user_content_entities | map(attribute='id') | list -%}
{% for entity in __user_content_entities -%}
{% for attr in entity.item_type.attributes if attr.x_ref and attr.x_ref.entity in node_ids -%}
{{ entity.id | mermaid_class_id }} --> {{ attr.x_ref.entity | mermaid_class_id }} : {{ attr.id }}
{% endfor -%}
{% endfor -%}
```
```

近傍図は `entity.id == focus_id or entity.id.startswith(focus_id ~ ".")` でフィルタする descendant 抽出パターンを追加 (`__meta_entity.md` / `__table_view.md` に既出)。per-query 図は `query.from` と `query.join[].to` から id 集合を組み、`__user_content_entities` を引き当てる。

#### タスク分割

実装規模を抑え、各段階で showcase/music を見て判断できるよう 3 PR に分ける:

- **F4a**: クエリ `__user_content_entities` 追加 + `mermaid_class_id` フィルタ + 全体図 (index.md)。基盤と最も汎用な配置を先行
- **F4b**: 近傍図 (`__meta_entity/<id>.md`)。主役属性表との重複を実物で判断
- **F4c**: per-query 図 (`__meta_query/<id>.md`)

