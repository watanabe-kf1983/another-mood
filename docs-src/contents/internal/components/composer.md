# Composer

## 処理フロー

1. `normalizedContentsDir` の *.yaml を読み込み、自動パススルーとして `viewsDir` にコピー
2. `normalizedQueriesDir` の *.yaml を読み込み、クエリを評価
   - 各クエリの `from` で参照するデータソースを `normalizedContentsDir` から取得
   - `grouped` → `select` の順に適用
3. クエリ評価結果を `viewsDir` に *.yaml として書き出し

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
