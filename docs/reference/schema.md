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

ルート直下に [マップパターン](#マップパターン)（`properties` を伴わない `additionalProperties: <スキーマ>`）は書けない（メタスキーマが拒否する）。

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

**排他制約**: 同じオブジェクト内で `properties` と `additionalProperties: <スキーマ>` は併用できない。`properties` を書く場合は `additionalProperties: false` が必須（メタスキーマがエラーにする）。

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
| `body` | `mime_type` と `content` を持つマップ。本文を埋め込むときはテンプレートから `.content` を参照する（例: `{{ body.content }}`） |

ソース Markdown は変換されずそのまま保たれるため、GitHub 上や IDE でそのまま閲覧・リンク遷移できる。

## schema-schema 全文

ここまでの本文は、内蔵メタスキーマ（schema-schema）を散文で解説したもの。厳密な仕様の正典は以下の YAML 本体。

```yaml
# $ref / $defs are used here for recursion, but are not available to
# user-defined schemas (only the keywords listed under jsonSchemaSubset are).

title: SchemaSchema
description: >-
  Meta-schema validating the user's definition/schema.yaml. The accepted
  language is a curated subset of JSON Schema draft 2020-12: the root must
  be an object with `properties:` enumerating each top-level entity, and
  only the keywords listed under jsonSchemaSubset are permitted. See
  docs/reference/schema.md for the prose specification.

$ref: "#/$defs/rootSchema"

$defs:
  rootSchema:
    title: Root schema constraints
    description: >-
      Constraints applied only at the root of the user's schema.yaml: it
      must be `type: object` and define `properties:`. A map-pattern root
      (additionalProperties without properties) is rejected because it
      would yield no entity to normalize.
    allOf:
      - $ref: "#/$defs/jsonSchemaSubset"
      - required: [properties]
        properties:
          type:
            const: object

  jsonSchemaSubset:
    title: Accepted JSON Schema subset
    description: >-
      Recursive subset of JSON Schema draft 2020-12 keywords accepted at
      every level of the user's schema. Structural keywords (type,
      properties, additionalProperties, items) are interpreted by the
      normalizer; validation, meta-data, and format keywords are passed
      through to the jsonschema library unchanged.
    type: object
    required: [type]
    properties:
      # --- Structural keywords (interpreted by this project) ---
      type:
        description: >-
          Single primitive type only. JSON Schema's array form
          (e.g. `[string, "null"]`) and the `null` type are rejected by
          design.
        type: string
        enum: [object, array, string, number, integer, boolean]
      properties:
        description: >-
          Fixed-structure object definition. When present at the same
          level, `additionalProperties: false` is required (see the
          `if`/`then` clause at the bottom); the map pattern
          (`additionalProperties: <schema>`) cannot be combined here.
        type: object
        propertyNames:
          description: >-
            Identifier pattern for property names: starts with a Unicode
            letter or underscore, followed by Unicode letters, digits, or
            underscores.
          pattern: "^[\\p{L}_][\\p{L}\\p{N}_]*$"
        additionalProperties:
          $ref: "#/$defs/jsonSchemaSubset"
      additionalProperties:
        description: >-
          Map-pattern signal. When set to a schema object, the value is
          a homogeneous map that the normalizer converts into an array.
          When set to `false`, no extra keys are allowed (required when
          `properties:` is present at the same level).
        anyOf:
          - $ref: "#/$defs/jsonSchemaSubset"
          - const: false
      items:
        description: Schema applied to each element of an array.
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

    # When `properties:` is present at the same level, `additionalProperties: false`
    # becomes required. Without `properties:`, `additionalProperties` may be a schema
    # object (the map pattern that drives map-to-array normalization).
    if:
      required: [properties]
    then:
      properties:
        additionalProperties:
          const: false
      required: [additionalProperties]
```

## content-schema 全文

[内蔵スキーマ: 散文](#内蔵スキーマ-散文-prose) で説明した prose エンティティの構造を定める内蔵スキーマ。本節の散文記述に対する正典。

```yaml
# Merged with the user's schema.yaml at validation time so that all
# content files are validated uniformly.

title: ContentSchema
description: >-
  Built-in schema that defines the `prose` entity. Markdown files under
  contents_dir are parsed into prose records (id, title, body) and
  validated alongside the user's schema.yaml.

type: object
properties:
  prose:
    title: Prose collection
    description: >-
      Collection of prose records, one per Markdown file in contents_dir.
      Each record carries the file's id, optional title, and parsed body.
    type: array
    items:
      title: Prose record
      description: One Markdown file parsed into an id / title / body triple.
      type: object
      properties:
        id:
          title: Prose id
          description: >-
            Stable identifier derived from the Markdown file's path
            (without extension).
          type: string
        title:
          title: Prose title
          description: >-
            Display title taken from the first H1 heading of the Markdown
            source. Absent when the source has no H1.
          type: string
        body:
          title: Prose body
          description: >-
            Body of the Markdown file, carrying its MIME type and the raw
            source text.
          type: object
          properties:
            mime_type:
              title: Body MIME type
              description: MIME type of the body content (currently always `text/markdown`).
              type: string
            content:
              title: Body content
              description: Raw Markdown source as a string.
              type: string
          required: [mime_type, content]
      required: [id, body]
```
