# SchemaInspector

スキーマ定義を解析し、データカタログ（フィールド一覧）を抽出する。
IN: `schema_file`
OUT: `inspect_schemas_dir`

## 目的

ユーザ定義スキーマ（JSON Schema サブセット）から、後続コンポーネントやメタドキュメンテーションが扱いやすいフラットな構造情報を抽出する。

JSON Schema のキーワード（`additionalProperties`, `properties`, `items` 等）をそのまま下流に渡すと、クエリやテンプレートが JSON Schema の構造を知る必要があり冗長になる（[normalizer.md](normalizer.md) 背景セクション参照）。SchemaInspector がこの変換を一手に引き受ける。

## 処理フロー

1. `schema_file` を読み込み
2. SchemaSchema でバリデーション（既存の `check_schema`）
3. スキーマからデータカタログを抽出
4. `inspect_schemas_dir` に `__definition` キーで出力

## データカタログの出力形状

→ [データカタログ出力形状](../../../data-catalog.md)（フィールド一覧・クラス図・ERD）

## 背景: なぜ木構造を経由するか

JSON Schema の構造パターン（`additionalProperties`, `properties`, `items`）とその組み合わせ（ネスト、配列の配列、スカラー辞書等）を直接データカタログに変換しようとすると、パターンごとの分岐が組み合わせ的に増える。木構造（SchemaTree）を中間表現にすることで:

- スキーマ → 木の変換は「JSON Schema → 3 種のノード」だけに集中でき、パターン追加時も局所的な変更で済む
- 木 → データカタログの変換は JSON Schema を意識せず、木の走査だけで生成できる

### dict_to_array との統合構想

SchemaTree は SchemaInspector（データカタログ抽出）だけでなく、Normalizer のデータ正規化（現 `dict_to_array`）にも利用できる。各ノードにデータ変換関数を持たせることで、木とデータを同時に走査するだけで正規化が完了する:

- **ObjectNode** → `_recurse_properties`（各フィールドに再帰）
- **ArrayNode（`array` 由来）** → `_recurse_items`（各要素に再帰）
- **ArrayNode（`additionalProperties` 由来）** → `_flatten_dict`（dict → array + id 付与）
- **ValueNode** → パススルー

SchemaTree の構築はスキーマを走査するだけの軽量処理なので、ステージ間でシリアライズせず、各ステージが `build_schema_tree(schema)` を呼んでそれぞれの用途に使う。共有するのはコード（関数）であってデータ（シリアライズされた木）ではない。
