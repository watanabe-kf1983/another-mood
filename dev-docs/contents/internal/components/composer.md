# Composer

## 処理フロー

1. `inspect_schema_dir` の *.yaml を読み込み、`__definition` 名前空間のまま `compose_dir` に passthrough（メタドキュメンテーション用、[meta-documentation.md](../../external/app/meta-documentation.md) 参照）
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
