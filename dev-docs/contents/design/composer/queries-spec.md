# Queries Specification

## External Design

### 背景: 永続化形式とクエリモデルの分離

著者がネスト（コンポジション）で書いたデータを、別の軸で再グループ化したいというニーズは、データの利用が進むにつれて事後的に現れる。`from` のドット記法は、著者の永続化形式（ネスト）を変更せずに、Composer のクエリモデル上でフラットなアクセスを可能にする。詳細は [json-data-model.md](../json-data-model.md) の「背景: なぜ永続化形式をフラット化しないか」を参照。

### 背景: where の closed set から `neq` (not equal) を外した理由

DB DSL によくある `neq` を入れなかったのは、対象キーが欠落しているレコードで何を返すべきかが、自然な読み方で 3 通りに分かれるため:

- 実データ上の `≠` と読めば **True** (値がないので x とは異なる)
- SQL の 3 値論理として読めば **UNKNOWN** (NULL の neq は UNKNOWN なので False 寄り)
- 「`eq` の論理否定」と読めば **True** (`eq` が False なので flip して True)

`neq` を closed set に入れると、どの解釈を採っても残り 2 つを期待した利用者から不自然に見える。代わりに「atomic 述語は欠落キーで常に False」+「`not` は内側の結果を flip」の 2 規則で semantics を一意化し、「等しくない」が必要なら `not: { field: x }` と書く設計にした。否定の挙動が `not` 1 箇所に集約され、述語ごとに考えなくてよくなる。

### 背景: sort の keyword に `null` ではなく `missing` を採用した

ツールの data model は「nullable は項目自体を省略する」が原則で、独立した「null 値」概念を持たない ([json-data-model.md](../json-data-model.md))。where 句も存在判定は `exists: true/false` で表現しており、`null` という語は DSL のどこにも出てこない。ここだけ SQL の `NULLS FIRST/LAST` を借用すると語彙が不揃いになる。`missing: first/last` は「missing key」をそのまま表現し、`exists` と語彙が並ぶ。ElasticSearch も `missing: _first/_last` を採用しており、JSON/YAML 上の DSL では先例がある。

### 背景: sort の `direction` × `missing` を直交にした上で default は direction 非依存にした

null/missing 位置の決め方は DB エンジン間で割れる。SQL 系は二派ある:

- direction 従属派 (MySQL, SQL Server, MongoDB, CouchDB 等): null を最大/最小値固定で扱い、`asc` / `desc` で位置が自動で決まる。明示パラメータを持たない
- 直交派 (PostgreSQL, Oracle, DuckDB, ElasticSearch, pandas): `NULLS FIRST/LAST` / `missing` / `na_position` を別パラメータで指定

本 DSL は後者を採る (前者なら `missing:` キーを設ける意味が薄い、かつ「null は値の一種」という SQL の前提が data model に合わない)。

直交派の中でもデフォルトはさらに分かれる:

- direction-dependent (PostgreSQL: `ASC NULLS LAST` / `DESC NULLS FIRST`、SQLite はその逆): 「null は最大値 (or 最小値)」という基底ルールから direction で導出される
- direction-independent (ElasticSearch, pandas: 常に `last`): direction 不問

本 DSL は後者を採る。「missing は末尾」が `asc` / `desc` どちらでも成り立つ不変条件で覚えられ、ユーザが「null は値として何位扱いか」を内面化する必要がない。

## Proposals

### 同名禁止 (E6)

クエリ名と正規化済みデータ名（テーブル名）の重複を禁止する（エラー）。クエリの `from:` は常に正規化済みデータ（テーブル）を指すため、同名を許すと循環参照が生じる。加工が必要な場合はクエリに別名を付ける。

> 現状は Composer が正規化済みデータと同名のクエリを silent に上書きする。Phase 10 タスク [E6](../../../tasks.md)。

### join (E3)

YAML DSL に `join` 句を追加する拡張候補。Phase 10 タスク [E3〜E4](../../../tasks.md)（仕様詰めが先）。

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

Join は **cardinality を変える** 操作なので、暗黙のデフォルトは silent な事故を招きやすい。`sort` の `missing: last` をデフォルト化したのとは温度が違い、ここはデフォルトを置かず明示させる方針。3 つの kind 名 (`nested` / `flat_inner` / `flat_left`) を毎回タイプすることが「結果の shape と cardinality を意識する」契機として機能する。

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
