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

**形式**: 構造化 YAML (式言語ではない)。top-level の複数キーは暗黙 AND、明示的に `or:` / `and:` で結合する。

```yaml
where:
  view: false                       # field: value は eq の sugar
  parent_entity: null               # field: null は is_null の sugar
  or:
    - id: categories
    - id: { startswith: 'categories.' }
```

**述語の閉じた集合**:

- スカラ等価: `eq`, `neq`, `is_null`
- 数値順序: `gt`, `gte`, `lt`, `lte`
- 文字列パターン: `startswith`, `endswith`, `contains`
- ブール結合: `and`, `or`

これより先 (算術、関数呼び出し、正規表現、ユーザ定義式) は入れない。境界を構文レベルで守るために式言語化を避けた。

**catalog 上の扱い**: `__definition.queries` の `where` attribute は `type: object` の opaque として登録する (attribute の `metadata` / `validation` と同じパターン)。recursive な構造を catalog の固定型モデルに乗せないため。`__meta_query` テンプレートでは `where` を `| to_yaml` でコードブロックとしてダンプする。

**`derive` への影響**: `where` は record をフィルタするだけで schema 形状を変えないため、`Query.derive` は where 句に対して identity (catalog transform 不要)。

#### 背景: 構造化 YAML を選んだ理由

候補は (a) 構造化 YAML / (b) SQL 風の式言語 string の二案。構造化を選んだ理由:

- 既存 DSL (`from:` / `select:` / `grouped:`) との一貫性
- JSON Schema 検証を既存の `query-schema.yaml` の延長で書ける
- YAML パーサが付ける位置情報 (`UserStr` 経由の diagnostic) がそのまま使える
- 構文レベルで「式が書けない」ため、算術や関数呼び出しへのスコープ膨張を物理的に止められる
- catalog 不整合 (where が opaque になる) は metadata/validation で既に確立されているパターンなので新規債務にならない

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
