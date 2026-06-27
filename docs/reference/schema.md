# Schema

The **schema** is the file that declares the types of structured data the project handles. A subset of JSON Schema (draft 2020-12) is written into a single file at `{project}/definition/schema.yaml`. Content files are validated against this declaration, and data written as maps is converted into arrays by **normalization** (covered below).

```yaml
# definition/schema.yaml
type: object
additionalProperties: false
properties:
  users:
    type: object
    additionalProperties:
      type: object
      additionalProperties: false
      properties:
        name: { type: string }
        email: { type: string }
      required: [name]
  orders:
    type: array
    items:
      type: object
      additionalProperties: false
      properties:
        title: { type: string }
        customer: { type: string }
```

## Root constraints

The root of the schema file must satisfy:

- `type: object` is required.
- `properties` is required. Each entry represents one **entity** (a collection of records of the same shape).
- `additionalProperties: false` is required (any undeclared top-level key becomes an error). The same pairing is required at every nested level: any `properties:` without `additionalProperties: false` causes a build error. The recommended style is to write `additionalProperties: false` on the line directly above each `properties:`.

A [map pattern](#map-pattern) (`additionalProperties: <schema>` without accompanying `properties`) is not allowed at the root level (the meta-schema rejects it).

A single fixed file. Splitting into multiple files or `$ref`-based references to external schemas is not supported.

## Three entity patterns

For the type of each entity (one entry under `properties`), choose from the following three patterns.

### Map pattern

Pattern for writing same-shaped records as a **map** (key-value pairs). When the schema describes a collection of homogeneous entries, this pattern is almost always the first choice.

Write a **schema object** (not `false`) as the value of `additionalProperties`:

```yaml
users:
  type: object
  additionalProperties:                  # ← map-pattern signal
    type: object
    additionalProperties: false
    properties:
      name: { type: string }
      email: { type: string }
    required: [name]
```

On the content file side, write a map:

```yaml
# contents/users.yaml
users:
  tanaka:
    name: Tanaka Taro
    email: tanaka@example.com
  suzuki:
    name: Suzuki Hanako
```

At build time this is **normalized**: the map keys are promoted to each record's `id` field, and the result becomes an array:

```yaml
users:
  - id: tanaka
    name: Tanaka Taro
    email: tanaka@example.com
  - id: suzuki
    name: Suzuki Hanako
```

What queries and templates reference is this normalized form.

**Nesting**: when an `additionalProperties` contains another `additionalProperties`, each level is recursively turned into an array.

```yaml
screens:
  type: object
  additionalProperties:
    type: object
    additionalProperties: false
    properties:
      title: { type: string }
      buttons:                           # nested map pattern
        type: object
        additionalProperties:
          type: object
          additionalProperties: false
          properties:
            label: { type: string }
```

**Non-object values**: when `additionalProperties` is something other than an object (e.g., `type: string`), each entry is normalized to `{ id: <key>, value: <value> }`.

### Array pattern

Pattern for an ordered sequence. Use `type: array` and write the element schema under `items`.

```yaml
tags:
  type: array
  items:
    type: object
    additionalProperties: false
    properties:
      name: { type: string }
```

On the content file side, write an array directly:

```yaml
tags:
  - name: important
  - name: draft
```

No normalization happens; the array you wrote is passed to templates as-is. Unlike the map pattern, **there is no implicit `id`**.

### Single-record pattern

Pattern for an object with predetermined keys and exactly one record (e.g., site settings). Enumerate the keys under `properties` rather than `additionalProperties`.

```yaml
site_config:
  type: object
  additionalProperties: false
  properties:
    title: { type: string }
    base_url: { type: string }
```

```yaml
site_config:
  title: My Site
  base_url: https://example.com
```

No normalization happens; the value is passed to templates as written.

**Exclusivity**: within the same object, `properties` and `additionalProperties: <schema>` cannot be combined. When `properties` is present, `additionalProperties: false` is required (the meta-schema raises an error otherwise).

## Supported keywords

A subset of JSON Schema draft 2020-12. Only the keywords listed below are accepted (unknown keywords are rejected uniformly by the built-in meta-schema's `additionalProperties: false`).

### Structural keywords (involved in normalization)

Keywords this tool interprets to determine the shape of data and the normalization behavior:

| Keyword | Role |
|---|---|
| `type` | The value's type (one of `object`, `array`, `string`, `number`, `integer`, `boolean`). |
| `properties` | Enumerated keys for the single-record pattern. |
| `additionalProperties` | Map-pattern signal, or `false`. |
| `items` | Schema for array elements. |

### Validation keywords

Keywords that express constraints on values. The tool does not interpret these; they are passed through to the jsonschema library:

- **Required fields**: `required`
- **Enumeration / constant**: `enum`, `const`
- **Numbers**: `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`
- **Strings**: `minLength`, `maxLength`, `pattern`
- **Arrays**: `minItems`, `maxItems`, `uniqueItems`

### Metadata keywords

Annotation keywords that do not affect validation or normalization:

- **Descriptions**: `title`, `description`
- **Examples**: `default`, `examples`
- **Lifecycle**: `deprecated`, `readOnly`, `writeOnly`

### Format

- `format` (e.g., `email`, `uri`). Retained as an annotation, but values are not validated against it.

### Entity references (x-ref)

`x-ref` declares that a property's value references a record in another top-level entity. It is an Another Mood extension (hence the `x-` prefix, following the OpenAPI/JSON Schema convention for non-standard fields).

```yaml
albums:
  type: object
  additionalProperties:
    properties:
      artist_id:
        type: string
        x-ref:
          entity: artists         # omitted attribute = target's `.id` (map pattern only)
      curator:
        type: string
        x-ref:
          entity: users
          attribute: name         # explicit attribute reference
```

Fields:

- `entity` (required) — name of a top-level entity.
- `attribute` (optional) — name of an attribute on the target entity. When omitted, the synthetic `.id` of a map-pattern target is referenced; the target must therefore use the [map pattern](#map-pattern). When the target uses the [array pattern](#array-pattern) (no implicit `id`), `attribute` is required.

Constraints:

- `x-ref` is only allowed on `type: string` properties.
- `entity` and `attribute` must refer to a target that exists in the catalog (otherwise the build fails).

At build time, every reference value in content data must point to an existing record in the target entity. Dangling references are reported as warnings: the build continues, with them listed at `output/__warnings/` (linked from `output/index.md`). Use [`mood build --strict`](cli.md#--strict) to fail the build on warnings.

The declared references appear in `output/__entity_defs/<entity>.md` as a `references` column.

## Unsupported keywords

Keywords that exist in JSON Schema draft 2020-12 but are rejected by the built-in meta-schema:

- **Core**: `$id`, `$schema`, `$ref`, `$defs`, `$anchor`, `$comment`, etc.
- **Composition and conditions**: `allOf`, `anyOf`, `oneOf`, `not`, `if` / `then` / `else`
- **Advanced applicators**: `patternProperties`, `prefixItems`, `contains`, `propertyNames`, `dependentSchemas`
- **Unevaluated**: `unevaluatedProperties`, `unevaluatedItems`
- **Other validation**: `minProperties`, `maxProperties`
- **Content**: `contentMediaType`, `contentEncoding`, `contentSchema`

## Other constraints

- `type` accepts a single string only. The array form such as `type: [string, "null"]` and the `null` type are not allowed.
- Property names under `properties` must be identifiers (Unicode letters, digits, underscores; no leading digit).

## Built-in schema: prose

Markdown files under `contents/` (`.md`, case-insensitive) are automatically normalized according to the **built-in prose schema**, without requiring a user-declared schema. One file = one record, all collected into the `prose` entity.

Record shape:

```yaml
prose:
  - id: "guides/ordering"              # relative path from contents_dir (without extension)
    title: "Ordering flow"             # text of the first H1 heading
    body:
      mime_type: text/markdown
      content: |
        # Ordering flow
        ...                             # the entire file (including the H1)
```

| Field | Value |
|---|---|
| `id` | Relative path from `contents_dir` (without extension). |
| `title` | Text of the first H1 heading. Omitted when there is no H1. |
| `body` | A map with `mime_type` and `content`. To embed the body, reference `.content` from a template (e.g., `{{ body.content }}`). |

The Markdown source files stay untouched on disk, so they remain browsable and traversable directly on GitHub or in your IDE. In the parsed `content`, relative links to other prose documents are normalized to their `node:` form (`[t](other.md)` → `[t](node:/prose/<id>)`) so the [`relink`](template.md#relink) filter resolves them to working URLs; every other link is kept as written.

## Full schema-schema

Everything above is a prose explanation of the built-in meta-schema (schema-schema). The strict specification is the YAML at [`./schemas/schema-schema.yaml`](./schemas/schema-schema.yaml).

## Full content-schema

The built-in schema that defines the structure of the prose entity introduced in [Built-in schema: prose](#built-in-schema-prose). The canonical specification is the YAML at [`./schemas/content-schema.yaml`](./schemas/content-schema.yaml).
