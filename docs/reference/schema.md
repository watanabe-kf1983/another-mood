# Schema

**スキーマ**は、プロジェクトで扱うデータの型を宣言するファイル。`{project}/definition/schema.yaml` 1 ファイルに、JSON Schema (draft 2020-12) のサブセットを書く。コンテンツファイルはこの宣言に照らして検証され、マップで書かれたデータは正規化（後述）で配列に変換される。

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

## ルートの制約

スキーマファイルのルートは次を満たす:

- `type: object` 固定
- `properties` 必須。各エントリが 1 つの **エンティティ**（同じ形のレコードの集まり）を表す
- 末尾に `additionalProperties: false`（宣言していないトップレベルキーをエラーにする）

ルート直下に [マップパターン](#マップパターン)（`properties` を伴わない `additionalProperties: <スキーマ>`）は書けない。エンティティ列挙モデルと整合せず、検証や正規化が黙って劣化するため、内蔵メタスキーマで明示的に弾く。

ファイルは 1 本固定。複数ファイルへの分割や外部スキーマの `$ref` 参照はサポートしない。

## エンティティの 3 パターン

各エンティティ（`properties` の 1 エントリ）の型として、次の 3 パターンを使い分ける。

### マップパターン

同じ形のレコードを **マップ**（キーと値のペア）で書くパターン。同型エントリの集まりを表すスキーマで、ほぼ常にこのパターンが第一選択になる。

`additionalProperties` の値に **スキーマオブジェクト**（`false` ではなく）を書く:

```yaml
users:
  type: object
  additionalProperties:                  # ← マップパターンのシグナル
    type: object
    properties:
      name: { type: string }
      email: { type: string }
    required: [name]
    additionalProperties: false
```

コンテンツファイル側はマップで書く:

```yaml
# contents/users.yaml
users:
  tanaka:
    name: 田中太郎
    email: tanaka@example.com
  suzuki:
    name: 鈴木花子
```

ビルド時に **正規化** され、マップキーが各レコードの `id` フィールドに昇格して配列になる:

```yaml
users:
  - id: tanaka
    name: 田中太郎
    email: tanaka@example.com
  - id: suzuki
    name: 鈴木花子
```

クエリやテンプレートが参照するのはこの正規化後の形。

**ネスト**: `additionalProperties` の中にさらに `additionalProperties` を入れると、各階層が再帰的に配列化される。

```yaml
screens:
  type: object
  additionalProperties:
    type: object
    properties:
      title: { type: string }
      buttons:                           # 入れ子のマップパターン
        type: object
        additionalProperties:
          type: object
          properties:
            label: { type: string }
          additionalProperties: false
    additionalProperties: false
```

**非オブジェクト値**: `additionalProperties` がオブジェクト以外（`type: string` など）の場合、各エントリは `{ id: <キー>, value: <値> }` の形に正規化される。

### 配列パターン

順序のある並びを表すパターン。`type: array` で、要素スキーマを `items` に書く。

```yaml
tags:
  type: array
  items:
    type: object
    properties:
      name: { type: string }
    additionalProperties: false
```

コンテンツファイル側は配列を直接書く:

```yaml
tags:
  - name: important
  - name: draft
```

正規化はかからず、書いた配列がそのままテンプレートに渡る。マップパターンと違い **暗黙の `id` を持たない**。

レコード数が増えたとき視認性で劣る・キー一意性が YAML 段階で保証されないため、外部から個別参照されない要素列（順序だけが意味を持つ手順、ID を考えるのが面倒なほど些末なレコードの羅列など）に向く。

### 単一レコードパターン

キーが事前に決まっていて、レコード数が 1 つのオブジェクト（サイト設定など）に使うパターン。`additionalProperties` ではなく `properties` でキーを列挙する。

```yaml
site_config:
  type: object
  properties:
    title: { type: string }
    base_url: { type: string }
  additionalProperties: false
```

```yaml
site_config:
  title: My Site
  base_url: https://example.com
```

正規化はかからず、書いた形のままテンプレートに渡る。

**排他制約**: 同じオブジェクト内で `properties` と `additionalProperties: <スキーマ>` は併用できない。`properties` を書く場合は `additionalProperties: false` が必須で、内蔵メタスキーマの `if/then` で強制される。

## サポートするキーワード

JSON Schema draft 2020-12 のサブセット。下記に挙げたキーワードのみ許容される（未知キーワードは内蔵メタスキーマの `additionalProperties: false` で一律エラー）。

### 構造キーワード（正規化に関与）

このツールが解釈し、データの形と正規化挙動を決定するキーワード:

| キーワード | 役割 |
|---|---|
| `type` | 値の型（`object` / `array` / `string` / `number` / `integer` / `boolean` のいずれか） |
| `properties` | 単一レコードパターンのキー列挙 |
| `additionalProperties` | マップパターンのシグナル、または `false` |
| `items` | 配列要素のスキーマ |

### バリデーションキーワード

値の制約を表現するキーワード。ツール側は解釈せず、jsonschema ライブラリにスルーパスする:

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

## サポートしないキーワード

JSON Schema draft 2020-12 にあるが、内蔵メタスキーマが拒否するキーワード:

- **Core 系**: `$id`, `$schema`, `$ref`, `$defs`, `$anchor`, `$comment` 等
- **合成・条件**: `allOf`, `anyOf`, `oneOf`, `not`, `if`/`then`/`else`
- **高度なアプリケーター**: `patternProperties`, `prefixItems`, `contains`, `propertyNames`, `dependentSchemas`
- **unevaluated**: `unevaluatedProperties`, `unevaluatedItems`
- **その他の validation**: `minProperties`, `maxProperties`
- **content**: `contentMediaType`, `contentEncoding`, `contentSchema`

## その他の制約

- `type` は単一文字列のみ。`type: [string, "null"]` のような配列形式や `null` 型は不可
- `properties` のキー（プロパティ名）は識別子（Unicode 文字・数字・アンダースコア、先頭は数字不可）

## 内蔵スキーマ: 散文 (prose)

`contents/` 配下の Markdown ファイル（`.md`、大小文字不問）は、ユーザがスキーマを宣言しなくても **内蔵 prose スキーマ** に従って自動的に正規化される。1 ファイル = 1 レコードで、`prose` エンティティに集約される。

レコードの形:

```yaml
prose:
  - id: "guides/ordering"              # contents_dir からの相対パス（拡張子なし）
    title: "注文の流れ"                  # 最初の H1 見出しテキスト
    body:
      mime_type: text/markdown
      content: |
        # 注文の流れ
        ...                             # ファイル全体（H1 含む）
```

| フィールド | 値 |
|---|---|
| `id` | `contents_dir` からの相対パス（拡張子を除く） |
| `title` | 最初の H1 見出しテキスト。H1 がなければ省略 |
| `body` | Typed Value（`mime_type: text/markdown` と `content`）。テンプレートからの埋め込みは [Template — Typed Value](template.md#typed-value-の取り扱い) を参照 |

ソース Markdown は変換されずそのまま保たれるため、GitHub 上や IDE でそのまま閲覧・リンク遷移できる。

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
      - required: [properties]
        properties:
          type:
            const: object

  jsonSchemaSubset:
    type: object
    required: [type]
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
