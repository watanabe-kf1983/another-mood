# Queries Specification

## External Design

### 背景: 永続化形式とクエリモデルの分離

著者がネスト（コンポジション）で書いたデータを、別の軸で再グループ化したいというニーズは、データの利用が進むにつれて事後的に現れる。`from` のドット記法は、著者の永続化形式（ネスト）を変更せずに、Composer のクエリモデル上でフラットなアクセスを可能にする。詳細は [json-data-model.md](../json-data-model.md) の「背景: なぜ永続化形式をフラット化しないか」を参照。

## Proposals

### 同名禁止 (E6)

クエリ名と正規化済みデータ名（テーブル名）の重複を禁止する（エラー）。クエリの `from:` は常に正規化済みデータ（テーブル）を指すため、同名を許すと循環参照が生じる。加工が必要な場合はクエリに別名を付ける。

> 現状は Composer が正規化済みデータと同名のクエリを silent に上書きする。Phase 10 タスク [E6](../../../tasks.md)。

### where / sort / join (E1-E4)

YAML DSL に `where`, `sort`, `join` 句を追加する拡張候補。Phase 10 タスク [E1〜E4](../../../tasks.md)（仕様詰めが先）。

#### where (E1)

**形式**: 構造化 YAML (式言語ではない)。top-level の複数キーは暗黙 AND、明示的に `or:` / `and:` / `not:` で結合する。

**評価順序**: `from → where → grouped → select`。SQL の WHERE/GROUP BY と同じく、record をフィルタしてから group する。

```yaml
where:
  view: false                       # field: value は eq の sugar
  or:
    - id: categories
    - id: { startswith: 'categories.' }
  not:
    id: { startswith: '__' }        # not は単一の whereClause を取る
```

**述語の閉じた集合**:

- フィールド述語 (atomic): `eq`, `gt`, `gte`, `lt`, `lte`, `startswith`, `endswith`, `contains`, `exists`
- 論理結合 (combinator): `and`, `or`, `not`

これより先 (算術、関数呼び出し、正規表現、ユーザ定義式) は入れない。境界を構文レベルで守るために式言語化を避けた。

**個別述語の意味**:

| 述語 | 値型 | 意味 |
|---|---|---|
| `eq` | 任意 | Python `==` で等価。型違いは常に False (`1 == "1"` は False)。`bool` と `int` の暗黙互換は Python 仕様通り。 |
| `gt`/`gte`/`lt`/`lte` | number | レコード値が **`int` または `float`** (bool 除く) のときのみ比較。それ以外の型は False (filter out)。文字列の lex 比較 (`"10" < "2"`) のような surprise を防ぐため、`isinstance` ガードと同じ扱いにする。 |
| `startswith`/`endswith`/`contains` | string | Python の `str.startswith` / `endswith` / `in` に対応。レコード値が文字列でなければ False (filter out)。 |
| `exists` | boolean | `true` ならキーがレコードに存在、`false` ならキー不在。**「キー欠落」を扱う唯一の述語**。 |

**キー欠落のセマンティクス**:

スキーマモデルが null 値を許さない（[schema-spec.md](../normalizer/schema-spec.md) の `type:` 列挙に `null` は含まない）ため、`required: false` 属性は **値が null** ではなく **キー自体が欠落** している状態として現れる。E1 の評価規則:

- **atomic 述語はキー欠落で常に False** (= レコードはフィルタアウト)
- **`exists` のみキー欠落に応答**: `{ exists: false }` でキー欠落レコードを True とする
- **`not` は内側の結果を flip**: `not { eq: "x" }` はキー欠落レコードでは `not False = True` を返し、フィルタに残す

この 2 規則で全 semantics が閉じる。例えば `not (exists: true)` と `exists: false` は等価。

**フィールド参照とドットパス**:

`where` のフィールド名は `select.item` / `grouped.by` と同じ `pluck` 経由で参照され、ドットパス (`hobby.active` など) で nested 属性に到達できる。catalog の dotted edge (singleton-flattened) も literal edge も longest-first match で同じ規則。

**catalog 上の扱い**: `__definition.queries` の `where` attribute は `type: object` の opaque として登録する (attribute の `metadata` / `validation` と同じパターン)。recursive な構造を catalog の固定型モデルに乗せないため。`__meta_query` テンプレートでは `where` を `| to_yaml` でコードブロックとしてダンプする。

**`derive` への影響**: `where` は record をフィルタするだけで schema 形状を変えないため、`Query.derive` は where 句に対して identity (catalog transform 不要)。

#### 背景: 構造化 YAML を選んだ理由

候補は (a) 構造化 YAML / (b) SQL 風の式言語 string の二案。構造化を選んだ理由:

- 既存 DSL (`from:` / `select:` / `grouped:`) との一貫性
- JSON Schema 検証を既存の `query-schema.yaml` の延長で書ける
- YAML パーサが付ける位置情報 (`UserStr` 経由の diagnostic) がそのまま使える
- 構文レベルで「式が書けない」ため、算術や関数呼び出しへのスコープ膨張を物理的に止められる
- catalog 不整合 (where が opaque になる) は metadata/validation で既に確立されているパターンなので新規債務にならない

#### 背景: `neq` / `is_null` / `null` sugar を closed set から外した理由

3 つの記法を採らない設計判断:

- **`neq` を入れない**: `not` + `eq` の合成で表現可能であり、`neq` を独立した atomic 述語とすると「キー欠落レコードを True/False どちらに倒すか」の答えが出ない（実データの neq とも、3VL の neq とも、論理否定の neq とも解釈できる）。`not` を直交した結合子として置き、「atomic 述語は欠落で False」+「`not` は flip」の 2 規則で全 semantics が決まる構造にする。
- **`is_null` を入れない / `field: null` sugar を入れない**: スキーマモデルが null を許さないので、利用者に `null` リテラルを書かせるのはモデルとのズレを意識させて不幸。「キー欠落」概念のみが存在し、それを表す唯一の手段として `exists` を採用する。
- **`exists` という名前**: MongoDB の `$exists` の慣習に合わせる。「キーが存在するか」の意味が誤読されにくい。

#### 背景: `not` を whereClause レベルの結合子として単一引数で配置する理由

`and:` / `or:` がリストを取るのに対し、`not:` は単一の whereClause を取る:

```yaml
where:
  not:
    id: { startswith: "__" }
```

`not: [...]` を許すと「`!(a∧b)` か `[¬a, ¬b]` か」が曖昧になる。リスト排除を構文レベルで強制すれば、利用者が `and:` / `or:` で結合してから `not` でくるむ流れが自然に促される。SQL/MongoDB/JSON Logic も同じ姿勢。

#### sort (E2)

**形式**: object (`grouped:` と対称)。

```yaml
sort:
  by: phase
  direction: desc       # asc (default) / desc
  nulls: last           # first / last (default: last)
```

**スコープ内**:

- 単一属性キー (`by:`)
- 方向: `asc` / `desc`
- null 配置: `nulls: first` / `nulls: last` (デフォルト `last`)

**スコープ外** (将来 Group By との合わせ技で検討):

- 複合キー / multi-column sort
- 派生式 (`id | split('.') | first` 等) によるソート
- カスタム比較関数

**catalog 上の扱い**: `__definition.queries` の `sort` attribute は scalar object としてフラット化され、`sort.by` / `sort.direction` / `sort.nulls` が attribute としてカタログ化される。`where` と異なり構造は固定なので opaque にはしない。

**`derive` への影響**: `sort` は record の順序のみ変えて schema 形状は変えないため、`Query.derive` は sort 句に対して identity。

#### 背景: nulls first/last を初版に含めた理由

将来「指定したくなる」ことが目に見えているため、後から syntax を増やす破壊的変更を避ける目的で初版から入れる。デフォルトを `last` にするのは PostgreSQL の `ASC NULLS LAST` 慣習に合わせる狙い (DESC でも `last` にすることで「null は常に末尾」という単純な不変条件で覚えられる)。

#### join (E3)

**形式**: list (常に list、単一 join でも要素 1)。

```yaml
from: cats
join:
  - to: tasks
    on: { left: id, right: cat }
    kind: nested                  # required, no default
    as: tasks
    filter:                       # optional, 右側 pre-filter (where と同じ構文)
      open: true
  - to: members
    on: { left: id, right: cat }
    kind: flat_inner
    as: members
```

**3 つの kind (required, no default)**:

| kind | 結果 shape | 子の無い親 |
|---|---|---|
| `nested` | 1 row per parent、子は配列で nest | 空配列で残る (LEFT OUTER 相当) |
| `flat_inner` | 1 row per match、cross-product | 消える |
| `flat_left` | 1 row per match、cross-product | NULL 充填されて残る |

cardinality を変える操作なので、デフォルトは置かず必ず明示させる。

**`on:` (初版スコープ)**:

- 単一キーペアの eq のみ: `{ left: <attr>, right: <attr> }`
- 複合キー、非 eq 比較 (gt / like 等) はスコープ外

**`as:` (required)**:

- `nested`: 結果配列 attribute の名前
- `flat_*`: 右側 attribute の名前空間 prefix (左との衝突を必ず避けるため)

**`filter:` (optional)**:

- 右側 relation への pre-filter。`where:` と同じ構造化 YAML
- 3 つの kind すべてで使える:
  - `nested`: 配列に入る子要素を絞る
  - `flat_*`: join 候補の右側 row を絞ってから結合

**多 join の semantics**:

- 左結合的に評価 (前の join 結果に対して順に適用)
- 後続 join の `on:` は前の join で持ち込まれた attribute を参照可能 (`tasks.assignee_id` 等、`as:` prefix 経由でアクセス)
- kind 混在は許容 (例: nested → flat_inner で cardinality 変化が起きる点だけ意図に注意)

**WHERE と JOIN の関係**:

- `where:` は常に **post-join** で評価
- 右側を pre-filter したい場合は `join[].filter:` を使う (SQL の `ON ... AND` 拡張と等価)
- 特に `flat_left` + 右側述語の post-WHERE は事実上 INNER に劣化する SQL の有名な罠と同じ — `filter:` を使えば回避できる

**スコープ外**:

- `on:` の複合キー、非 eq 比較
- 多重 NESTED (3+ 階層の動的 nest) — 将来必要が見えた時に再検討。固定構造の親子は既存の `from:` ドット記法でカバー済
- FK 自動推論 (ORM 風の `on:` 省略)

**`Query.derive` への影響**:

`where` / `sort` と異なり identity ではない。3 つの kind それぞれが固有の catalog transform を持つ:

- `nested`: 左 catalog に `as:` 名の `object[]` child attribute を追加
- `flat_*`: 左の attribute と (`as:` prefix 付きの) 右の attribute をマージした row 型に変換

#### 背景: 3 択を required にした理由 (join)

Join は **cardinality を変える** 操作なので、暗黙のデフォルトは silent な事故を招きやすい。`E2` の `nulls last` をデフォルト化したのとは温度が違い、ここはデフォルトを置かず明示させる方針。3 つの kind 名 (`nested` / `flat_inner` / `flat_left`) を毎回タイプすることが「結果の shape と cardinality を意識する」契機として機能する。

#### 背景: `filter:` を `where:` から分離した理由

SQL の `ON` と `WHERE` の使い分けと同じ問題が DSL でも発生する。`flat_left` + 右側述語の post-WHERE が事実上 INNER に劣化する罠を、構文レベルで分離することで避けやすくする。`filter:` を使うか `where:` を使うかが、そのまま「outer の semantic を保つか / join 後の結果に対する filter か」の意図表明になる。

実装上は `join[].filter:` は「右側 relation に対する where のみ書ける糖衣構文」で、`to:` に full sub-query を許す案 (= 右側で sort/group/select も書ける) の strict subset。実用上 join の右側で必要な操作は filter にほぼ集約されるため、フルの sub-query 機構を導入せずに済む節約になる。

#### 背景: FK 自動推論を採用しない理由

ActiveRecord / Django ORM / SQLAlchemy 等の ORM では、FK 関係が宣言されていると `on:` 相当を自動推論する仕組みが一般的。便利だが、本 DSL は「狭く明示的に置く」方針 (式言語化を避ける、join の kind を required にする等と同じ系統)。`on:` も同様に常に明示させる。

参照整合性 (D タスク群) で FK が導入された後も、`on:` を省略可能にする方向には進めない。

### `_parent` 親参照 (M1)

`from` のドット記法でフラット化された各オブジェクトに `_parent` を付与し、親オブジェクトにアクセス可能にする（[json-data-model.md](../json-data-model.md) 参照）。

例: タスクをフェーズ別にグループ化する際にカテゴリ名（親）を表示する。

```yaml
# queries/tasks-by-phase.yaml
tasks_by_phase:
  from: categories.tasks
  grouped:
    by: phase
  select:
    - item: phase
      as: id
    - item: phase
    - item: tasks
```

```jinja2
{# templates/tasks-by-phase.md #}
{% for group in tasks_by_phase %}
## Phase {{ group.phase }}
| ID | タスク | カテゴリ | 状態 |
|---|---|---|---|
{% for task in group.tasks -%}
| {{ task.id }} | {{ task.title }} | {{ task._parent.title }} | {{ "✅" if task.done else "-" }} |
{% endfor %}
{% endfor %}
```

> 現状は `_parent` の付与自体が未実装のため、`task._parent.title` は空文字としてレンダリングされる。Phase 10 タスク [M1](../../../tasks.md)。
