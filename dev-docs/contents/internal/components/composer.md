# Composer

## 処理フロー

1. `inspect_schemas_dir` の *.yaml を読み込み、`__definition` 名前空間のまま `compose_dir` に passthrough（メタドキュメンテーション用、[meta-documentation.md](../../design/app/meta-documentation.md) 参照）
2. `normalize_contents_dir` の *.yaml を読み込み、自動パススルーとして `compose_dir` にコピー
3. `normalize_queries_dir` の *.yaml を読み込み:
   - クエリ定義そのものを `__definition.queries` として `compose_dir` に passthrough
   - 各クエリを評価し、結果を `compose_dir` に *.yaml として書き出し
   - 各クエリの `from` で参照するデータソースは `normalize_contents_dir` から取得
   - `grouped` → `select` の順に適用

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

> **未着手** — F3 (Query View) で対応予定。本節は方針の備忘。

Query オブジェクトは同じ DSL (from / grouped / select / 将来の where / sort / join) から導かれる **2 つの変換**を定義している:

1. **raw Data の結合・加工**: 入力データ行の集合 → 結果データ行の集合（現行の `Query.apply`）
2. **raw DataCatalog の結合・加工**: 入力スキーマ群（`__definition.entities[].fields`）→ 結果スキーマ（`__definition.queries[].fields`）

この 2 つは同じ DSL から派生するペア変換であり、同一の Query オブジェクトが両方のメソッドを持つのが自然:

```python
class Query:
    def apply(self, sources) -> Records: ...           # 既存
    def apply_to_catalog(self, catalog) -> Fields: ...  # F3 で追加
```

### 配置

- **Normalizer**: 意味論的バリデーション（select の参照先 field が存在するか等）のみ。Query オブジェクトの構築・実行には踏み込まない
- **Composer**: Query オブジェクトを構築し、両方の apply を呼ぶ:
  - `apply(sources)` → 実データ view（既存）
  - `apply_to_catalog(catalog)` → `__definition.queries[].fields` に流し込み

### `apply_to_catalog` が実データを参照しないことの意義

実データがまだ存在しない段階でもカタログ側だけ先に組めるため、テンプレート著者は watch 中にクエリ DSL を書き換えながら結果スキーマを俯瞰できる。実データ評価がコケてもカタログは更新される。

このため、Composer 内部のステップ順序として「カタログ生成 → 実データ評価」を明示的に分け、前段が独立して成功するよう実装する。
