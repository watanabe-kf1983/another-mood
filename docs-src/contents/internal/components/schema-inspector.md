# SchemaInspector

スキーマ定義を解析し、データカタログ（フィールド一覧）を抽出する。
IN: `schemaDir`
OUT: `dataCatalogDir`

## 目的

ユーザ定義スキーマ（JSON Schema サブセット）から、後続コンポーネントやメタドキュメンテーションが扱いやすいフラットな構造情報を抽出する。

JSON Schema のキーワード（`additionalProperties`, `properties`, `items` 等）をそのまま下流に渡すと、クエリやテンプレートが JSON Schema の構造を知る必要があり冗長になる（[normalizer.md](normalizer.md) 背景セクション参照）。SchemaInspector がこの変換を一手に引き受ける。

## 処理フロー

1. `schemaDir` の全 YAML ファイルを読み込み・マージ
2. SchemaSchema でバリデーション（既存の `check_schema`）
3. スキーマからデータカタログを抽出
4. `references` をそのまま転記
5. `dataCatalogDir` に `__definition` キーで出力

## データカタログの出力形状

→ [データカタログ出力形状](../../../data-catalog/overview.md)（フィールド一覧・クラス図・ERD）

### フィールドの抽出ルール

スキーマの構造パターンに応じて、再帰的にフィールドとエンティティを抽出する:

- **`type: object` + `properties`**
  - 自分自身を `object` 型フィールドとして追加
  - 自分の名前を prefix に、再帰的に `properties` からフィールドを収集

- **`type: object` + `additionalProperties`**
  - 自分自身を `object[]` 型フィールドとして追加
  - 自分自身をエンティティとしてとらえ直し、`additionalProperties` からフィールドを収集（`id` フィールドはスキーマに明示されていないが、暗黙的に宣言されているものとして追加する）

- **`type: array` + `items.type: object`**
  - 自分自身を `object[]` 型フィールドとして追加
  - 自分自身をエンティティとしてとらえ直し、`items` からフィールドを収集（`id` フィールドはつけない）

- **`type: array` + `items.type` が object 以外**
  - 自分自身を `${items.type}[]` 型フィールドとして追加

- **`type` が `array`・`object` 以外**
  - 自分自身をフィールドとして追加

### references

入力の `references` をそのまま転記する。

## 出力例

example-project のスキーマを入力とした場合:

```yaml
__definition:
  entities:
    entities:
      fields:
        id:
          type: string
          required: true
        name:
          type: string
          required: true
        category:
          type: string
          required: false
        description:
          type: string
          required: false
        fields:
          type: object[]
          required: true

    entities.fields:
      fields:
        id:
          type: string
          required: true
        name:
          type: string
          required: true
        type:
          type: string
          required: true
        pk:
          type: boolean
          required: false
        fk:
          type: string
          required: false

    relations:
      fields:
        from:
          type: string
          required: true
        to:
          type: string
          required: true
        cardinality:
          type: string
          required: true
        description:
          type: string
          required: false

  references:
    - from: entities.fields
      to: entities.fields
    - from: relations.from
      to: entities
    - from: relations.to
      to: entities
```

