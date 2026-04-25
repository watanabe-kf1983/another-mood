# Schema

**スキーマ**（schema）は、プロジェクトで扱うデータの型宣言。扱いたいエンティティ（ユーザ、注文、画面など、データの種類）ごとに、どんなフィールドを持ちどんな構造を取るかを書く。コンテンツはこの宣言に照らして検証され、辞書で書かれたデータは配列に正規化される（後述）。

スキーマは `{project}/definition/schema.yaml` 1 ファイルに、JSON Schema (draft 2020-12) のサブセットを書く。ルートは `type: object` で、`properties:` 配下の各エントリがコンテンツ全体における 1 つのエンティティ（コレクション）に対応する。

```yaml
# definition/schema.yaml
type: object
properties:
  users:
    type: object
    additionalProperties:
      type: object
      properties:
        name: { type: string }
        email: { type: string }
      required: [name]
      additionalProperties: false
  orders:
    type: array
    items:
      type: object
      properties:
        title: { type: string }
        customer: { type: string }
      additionalProperties: false
additionalProperties: false
```

ファイルは 1 本固定。複数ファイルへの分割や外部スキーマの `$ref` 参照はサポートしない。コンテンツ YAML はこのスキーマの**部分インスタンス** (`properties` の一部のキーのみを持つオブジェクト) として valid である必要がある。1 ファイルに複数のトップレベルキーを同居させてもよい。

本章は、付録の [schema-schema 全文](#schema-schema-全文)（スキーマ定義の形を縛る内蔵メタスキーマ）を散文で解説したもの。厳密な仕様は付録の YAML が正典となる。

## サポートするキーワード

JSON Schema draft 2020-12 のサブセット。ここに挙げたキーワードのみ許容される。

### 構造キーワード（辞書→配列変換に関与）

このツールが独自に解釈し、データの形と正規化挙動を決定するキーワード:

| キーワード | 役割 |
|---|---|
| `type` | 値の型（`object` / `array` / `string` / `number` / `integer` / `boolean` のいずれか） |
| `properties` | 固定構造のキー列挙 |
| `additionalProperties` | 辞書パターンのシグナル、または `false` |
| `items` | 配列要素のスキーマ |

これらを組み合わせて、データの 3 つの形を表現する: **辞書パターン**・**固定構造パターン**・**type: array**。

#### 辞書パターン（additionalProperties）

同型エントリの集まりを表すスキーマ。`additionalProperties` に**スキーマオブジェクト**（`false` ではなく）を書く。

```yaml
type: object
properties:
  users:
    type: object
    additionalProperties:
      type: object
      properties:
        name: { type: string }
        email: { type: string }
      required: [name]
      additionalProperties: false
additionalProperties: false
```

コンテンツ側は辞書で書く:

```yaml
# contents/users.yaml
users:
  tanaka:
    name: 田中太郎
    email: tanaka@example.com
  suzuki:
    name: 鈴木花子
```

正規化で配列にフラット化され、辞書キーが `id` フィールドとして現れる:

```yaml
users:
  items:
    - id: tanaka
      name: 田中太郎
      email: tanaka@example.com
    - id: suzuki
      name: 鈴木花子
```

**ネスト**: `additionalProperties` の中に入れ子で `additionalProperties` を書けば、各階層が再帰的に配列化される。

```yaml
type: object
properties:
  screens:
    type: object
    additionalProperties:
      type: object
      properties:
        title: { type: string }
        buttons:                    # 入れ子の辞書パターン
          type: object
          additionalProperties:
            type: object
            properties:
              label: { type: string }
            additionalProperties: false
      additionalProperties: false
additionalProperties: false
```

#### 固定構造パターン（properties）

キーと型が事前に決まっているオブジェクト。`properties` でキーを列挙する。正規化の対象外で、書いた形のままパススルーされる。

```yaml
type: object
properties:
  site_config:
    type: object
    properties:
      title: { type: string }
      base_url: { type: string }
    required: [title]
    additionalProperties: false
additionalProperties: false
```

**排他制約**: 同じオブジェクト内で `properties` と `additionalProperties: <スキーマ>` は併用できない。`properties` を書く場合は `additionalProperties: false` が必須で、schema-schema の `if/then` で強制される。

#### type: array

配列型のトップレベルスキーマ。要素スキーマは `items` で指定する。コンテンツ側は配列を直接書く。

```yaml
type: object
properties:
  tags:
    type: array
    items:
      type: object
      properties:
        name: { type: string }
      additionalProperties: false
additionalProperties: false
```

辞書パターンと違い、配列型は**暗黙の `id` を持たない**。

### バリデーションキーワード

値の制約を表現するキーワード。プロジェクトは解釈せず、jsonschema ライブラリにそのままスルーパスする:

- **必須フィールド**: `required`
- **列挙・定数**: `enum`, `const`
- **数値**: `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`
- **文字列**: `minLength`, `maxLength`, `pattern`
- **配列**: `minItems`, `maxItems`, `uniqueItems`

### メタデータキーワード

検証・正規化には影響しない、注釈用のキーワード:

- **説明**: `title`, `description`
- **例示**: `default`, `examples`
- **ライフサイクル**: `deprecated`, `readOnly`, `writeOnly`

### フォーマット

- `format`（`email`, `uri` など）。アノテーションとして保持されるが、値の検証は行わない

## 制約事項

### サポートしないキーワード

JSON Schema draft 2020-12 にあるが、このツールでは拒否されるキーワード（schema-schema の `additionalProperties: false` により未知キーワードは一律エラー）:

- **Core 系**: `$id`, `$schema`, `$ref`, `$defs`, `$anchor`, `$comment`
- **合成・条件**: `allOf`, `anyOf`, `oneOf`, `not`, `if`/`then`/`else`
- **高度なアプリケーター**: `patternProperties`, `prefixItems`, `contains`, `propertyNames`, `dependentSchemas`
- **unevaluated**: `unevaluatedProperties`, `unevaluatedItems`
- **その他の validation**: `minProperties`, `maxProperties`
- **content**: `contentMediaType`, `contentEncoding`, `contentSchema`

また以下のルールがある:

- `type` は単一文字列のみ（`type: [string, "null"]` のような配列形式や `null` 型は不可）
- スキーマ名およびプロパティ名は識別子（Unicode 文字・数字・アンダースコア、先頭は数字不可）
- ルートは `type: object` 固定で `properties:` を必ず持つ。ルート直下に辞書パターン（`additionalProperties: <スキーマ>`）は書けない（エンティティ列挙モデルと整合しないため）

## schema-schema 全文

スキーマ定義の形を縛る内蔵メタスキーマ。本章の正典。

```yaml
# SchemaSchema — built-in meta-schema that validates the user's schema.yaml.
#
# The user's schema.yaml is a JSON Schema (draft 2020-12) subset whose
# root is `type: object` with `properties:` listing each top-level
# entity collection.  See dev-docs schema-spec.md for the full list of
# supported keywords.
#
# This meta-schema uses $ref/$defs for recursion, which is NOT available
# to user-defined schemas.  The restriction is intentional: user schemas
# go through normalization and visualization pipelines that cannot handle
# $ref; this built-in schema is only consumed by the jsonschema validator.

$ref: "#/$defs/rootSchema"

$defs:
  # The root user schema is a jsonSchemaSubset with two extra constraints:
  # type must be `object` and `properties:` must be present.  This rules
  # out a dict-pattern root (`additionalProperties: <schema>` without
  # `properties:`), which would otherwise pass validation but degrade
  # silently downstream — extract_data_catalog yields no entities and
  # the normalizer ignores the root additionalProperties because
  # _build_object_from_properties is preferred once the user schema is
  # merged with the built-in prose schema (which contributes properties).
  rootSchema:
    allOf:
      - $ref: "#/$defs/jsonSchemaSubset"
      - required: [type, properties]
        properties:
          type:
            const: object

  jsonSchemaSubset:
    type: object
    properties:
      # --- Structural keywords (interpreted by this project) ---
      type:
        type: string
        enum: [object, array, string, number, integer, boolean]
      properties:
        type: object
        propertyNames:
          pattern: "^[\\p{L}_][\\p{L}\\p{N}_]*$"
        additionalProperties:
          $ref: "#/$defs/jsonSchemaSubset"
      additionalProperties:
        anyOf:
          - $ref: "#/$defs/jsonSchemaSubset"
          - const: false
      items:
        $ref: "#/$defs/jsonSchemaSubset"

      # --- Validation keywords (pass-through to jsonschema) ---
      required:
        type: array
        items: { type: string }
        uniqueItems: true
      enum:
        type: array
        minItems: 1
      const: {}
      minimum: { type: number }
      maximum: { type: number }
      exclusiveMinimum: { type: number }
      exclusiveMaximum: { type: number }
      multipleOf: { type: number, exclusiveMinimum: 0 }
      minLength: { type: integer, minimum: 0 }
      maxLength: { type: integer, minimum: 0 }
      pattern: { type: string }
      minItems: { type: integer, minimum: 0 }
      maxItems: { type: integer, minimum: 0 }
      uniqueItems: { type: boolean }
      # --- Meta-data keywords (pass-through) ---
      title: { type: string }
      description: { type: string }
      default: {}
      examples: { type: array }
      deprecated: { type: boolean }
      readOnly: { type: boolean }
      writeOnly: { type: boolean }

      # --- Format annotation (pass-through) ---
      format: { type: string }

    additionalProperties: false

    # When properties is defined, additionalProperties: false is required.
    # When properties is absent, additionalProperties can be a schema object
    # (dict pattern for dict-to-array normalization).
    if:
      required: [properties]
    then:
      properties:
        additionalProperties:
          const: false
      required: [additionalProperties]
```
