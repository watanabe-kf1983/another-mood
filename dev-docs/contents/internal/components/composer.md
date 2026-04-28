# Composer

## 処理フロー

1. `inspect_schemas_dir` の *.yaml を読み込み、`__definition` 名前空間のまま `compose_dir` に passthrough（メタドキュメンテーション用、[meta-documentation.md](../../design/app/meta-documentation.md) 参照）
2. `normalize_contents_dir` の *.yaml を読み込み、自動パススルーとして `compose_dir` にコピー
3. `derive_queries_dir` の *.yaml を読み込み:
   - `__definition.queries` および `__definition.entities`（派生エンティティ。Query Deriver で生成済み）を `compose_dir` にそのまま passthrough
   - 各クエリを `normalize_contents_dir` から取得した contents に対して評価し、結果を `compose_dir/query-results/{id}.yaml` に書き出し
   - `from` → `grouped` → `select` の順に適用

### クエリ評価の詳細

**grouped**: `by` フィールドでオブジェクト配列をグループ化する。Python の `itertools.groupby` 相当。

1. ソース配列を `by` フィールドの値で分類
2. 各グループを `{<by>: <key値>, <as>: [<グループ内要素>]}` の形に変換
3. `as` 省略時は `from` の値をデフォルト名として使用

**select**: 出力フィールドを選択する。

1. `grouped` の結果（またはソース配列）の各要素に対して適用
2. 各要素は `item` でフィールドを指定、`as` でリネーム（省略時は `item` の値）
3. `select` に含まれないフィールドは出力されない
4. `select` 省略時は空オブジェクトの配列

## Query Object の双対性

Query オブジェクトは同じ DSL (from / grouped / select / 将来の where / sort / join)
から導かれる **2 つの変換**を持つ:

1. **raw Data の結合・加工**: 入力データ行の集合 → 結果データ行の集合 (`Query.apply`)
2. **raw DataCatalog の結合・加工**: 入力スキーマ → 結果スキーマ (`Query.derive`)

両者は同じ DSL から派生するペア変換であり、同一の Query オブジェクトが両方のメソッドを持つ:

```python
class Query:
    def apply(self, sources) -> Records: ...
    def derive(self, catalog) -> Node: ...
```

### 合成 child entity

composite フィールド (`object[]` / `entity` ref 持ち) を query 出力に含む場合、
`entity` ref は source entity をそのまま指すのではなく、**query 側で自分の子を
合成して `__definition.entities` に追記**する。命名は raw entity と揃えた
`{query_id}.{attribute_id}` 形式 (例: `tasks_by_phase.tasks`)。

合成 entity が `__definition.entities` に乗ると、既存 `__root.md` のループが
`__meta_entity` / `__table_view` を自動生成し、navigation は raw entity と
uniform になる。

現行 DSL (from / grouped / select) の範囲では合成 entity の records は
source entity の records と集合として同一 (並び替え / 射影のみで records は
増減しない)。冗長に見えるが、where (E1) / join (E3) が入れば source と異なる
独自データを持つので、合成の仕組みを先に入れておく。

### `derive` が実データを参照しないことの意義

データ無しでもカタログだけ先に組めるので、テンプレート著者は watch 中に
クエリ DSL を書き換えながら結果スキーマを俯瞰できる。`derive` は Query Deriver
ステージで実行され、`apply` だけが Composer の責務として残る。

### 配置

- **Query Deriver**: スキーマ検証 + `Query.derive`（派生エンティティ生成）
- **Composer**: `Query.apply`（実データ評価）と passthrough のみ
