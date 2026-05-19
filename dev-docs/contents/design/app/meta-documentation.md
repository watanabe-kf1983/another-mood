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

### ER 図 (F4)

Phase 10 タスク [F4](../../../tasks.md)。前提 D, E3, Mermaid エスケープ。
