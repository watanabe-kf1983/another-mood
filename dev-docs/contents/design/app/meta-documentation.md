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

## Proposals

### ER 図 (F4)

Phase 10 タスク [F4](../../../tasks.md)。前提 D, E3, Mermaid エスケープ。

### Query 化リファクタ (F7)

> **未実装** — Phase 10 タスク [F7](../../../tasks.md)。前提 [F8](../../../tasks.md) (カタログ自己記述) と E1〜E4 (where / sort / join) の DSL 拡張。

現在の `__meta_entity` / `__table_view` / `__meta_query` テンプレートは Jinja2 内に `rejectattr('view')`, `startswith` による子孫マッチ, `type == 'object'` 除外といった集計ロジックを抱え複雑化している。

これらを Query DSL 側に移し (`__definition.entities` 自体を `from` に取れるようにするのも含む)、テンプレートは Query 結果をテーブルに流すだけの薄いラッパに退化させたい。同時に本ツール自身のメタドキュメンテーションを自前の DSL で構築できるようになり、dog-fooding の度合いが上がる。

F7 が必要とする最小限の DSL 語彙の見立て:

- `from: __definition.entities` — カタログ自体を query 源として開く (F8 で扱う)
- `where` — 等価・null 判定で `view=false` / `parent_entity is null` / `type != 'object'` 等を表現 (E1)
- 子コレクションへの `where` — `__definition.entities.item_type.attributes` をフラット化して `from:` に取り、where で属性フィルタを表現することで賄える見込み
- `sort` — built-in flag 等での並び替え (E2)
- `join` — entity と view 行の結合 (現在の `__views | query_from(id)` の置き換え, E3)

scalar object 中間ノード (例 `__definition.entities.item_type`) はカタログのフラット化ルールにより独立 entity にならず、attribute がドット名で親に flatten される。よって catalog 上に立つ自己記述 entity は `__definition.entities` / `__definition.entities.item_type.attributes` / `__definition.queries` / `__definition.queries.select` に集約される (詳細は F8)。

### `__definition` の自己記述カタログ (F8)

> **未実装** — Phase 10 タスク [F8](../../../tasks.md)。F7 の前提。本タスク自体は [E8](../composer/queries-spec.md#from-パス解決の最長一致化-e8) (パス解決の最長一致化) を前提とする。

#### 自己記述レコードの構築: dataclass の classmethod で組み立てる

カタログの persisted form を表現する authoritative な JSON Schema は無く、Single Source of Truth は `data_catalog.py` の dataclass (`Entity` / `ObjectType` / `Attribute`) および `query.py` のクエリ DSL クラス。自己記述カタログは、それぞれの SSoT クラスにクラスメソッドを持たせて Python 上で `dc.Entity` レコードを直接構築する:

- `dc.Entity.get_catalog() -> Sequence[Entity]` — Schema 側 (`__definition.entities` および `__definition.entities.item_type.attributes`)
- `Query.get_catalog() -> Sequence[Entity]` — Query 側 (`__definition.queries` および `__definition.queries.select`)

採用理由:

- 自己記述は被記述者 (dataclass) の近傍に置く。Schema 側を `data_catalog.py`、Query DSL 側を `query.py` がそれぞれ責任を持つ
- 既存 built-in (prose) は JSON Schema → catalog 変換だが、`__definition` には対応する authoritative な JSON Schema が存在しない。YAML 直書き案は dataclass との二重定義になる。Python 構築なら dataclass フィールド情報を一部 reflection で活用可能 (`dataclasses.fields(...)`) で drift 抑制が利く
- `__definition.queries` への entity 参照は `Entity.get_catalog()` 内で id 文字列リテラルとして書く (`query.py` を import せず ID 規約だけ知る)。合流は call site で `[*Entity.get_catalog(), *Query.get_catalog()]`

#### `__definition` root 自体はカタログに載せない

ユーザ領域では、トップレベル singleton (= スキーマルート) はカタログに entity として現れず、その直下のコレクションが top-level entity (`parent_entity=null`) として並ぶ。これと同じ構造を `__definition` にも適用し、`__definition` 自身はカタログに含めない。

`__definition.entities` / `__definition.queries` は dotted id を持つ top-level entity (`parent_entity=null`) として登録する。`from: __definition.entities` は E8 のパス解決最長一致化を前提に解決される。

#### パイプライン上の取り込み箇所

`inspect_schema` を拡張し、`Entity.get_catalog() + Query.get_catalog()` の合算を `out_dir/__builtin/__definition.yaml` として YAML 化する。既存の prose built-in と同じ流路。`watch_paths` に監視対象が無い静的内容のためだけに専用 component を新設する利点が無い、という判断。

`composer` 側は `sources = load_model(contents_out, data_catalog_out, queries_out)` に拡張する。これだけで `sources["__definition"] = {"entities": [...], "queries": [...]}` が deep-merge 規約により自動で組まれ、`From.apply` が `__definition.*` を walk 可能になる。専用の合流ロジックは書かない。

#### dataclass との drift 抑制

`get_catalog()` の出力と dataclass のフィールド集合の対応をテストで突き合わせる方針 (具体形は実装後に判断)。`dataclasses.fields(dc.Entity)` 等で得た field 集合と、自己記述カタログ上の `__definition.entities` 直下 attribute id 集合の対応を assert する形が候補。
