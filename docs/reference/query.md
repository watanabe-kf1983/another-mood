# Query

A **query** is a mechanism that reshapes structured data into a more convenient form for reference, producing a named **view**. Queries can express grouping, field projection, and similar transformations.

Queries live in YAML files under `{project}/definition/queries/` (`.yaml` or `.yml`, case-insensitive). The number of files, how they are split, and any subdirectory layout are flexible; all queries are evaluated together at build time. A single file can hold multiple queries — each top-level key becomes a view name.

## Basic query structure

Structure of a view definition:

```yaml
# queries/by_role.yaml
by_role:                     # ← top-level key of the file becomes the view name
  from: members              # required
  where:                     # optional
    active: true
  grouped:                   # optional
    by: role
  select:                    # optional
    - item: role
      as: id
    - item: role
    - item: members
```

| Clause | Required | Role |
|---|---|---|
| `from` | Required | Source data (what to operate on). |
| `flatten` | Optional | Unwind one or more intrinsic array attributes. |
| `where` | Optional | Per-record filter applied before grouping. |
| `grouped` | Optional | Grouping of records. |
| `select` | Optional | Projection of output fields. When omitted, the result is an array of empty objects. |
| `sort` | Optional | Ordering of the final output records. |

Evaluation order: `from` → `flatten` → `where` → `grouped` → `select` → `sort`.

## Automatic pass-through

Data for entities declared in [Schema](schema.md) is automatically passed through and can be referenced from templates by entity name without writing any query. Queries are only needed when you want an additional view (grouping, projection, and so on).

## from

Specifies the entity to read from. The value is the entity name (= the top-level key in source YAML, declared under `properties` in schema.yaml).

```yaml
from: members
```

To read from a child entity, name the parent here and use [`flatten:`](#flatten) to descend.

## flatten

Unwinds one or more intrinsic array attributes. Each input row produces N output rows, where N is the length of the array at `of:`: the row's other fields are repeated verbatim across all N copies, and each copy gets one of the array's elements placed under `as:`. Runs between `from:` and `where:`.

```yaml
# Single attribute, scalar shorthand
from: categories
flatten: tasks                     # 1 row per task; element placed under `tasks`

# Single attribute, object form
from: categories
flatten:
  of: tasks
  as: task                         # rename the element namespace
  preserve_empty: true             # keep parents whose array is empty or missing

# Multiple attributes, list form (each later entry sees the row shape
# produced by earlier ones)
from: members
flatten:
  - hobbies
  - { of: pets, as: pet }
```

| Key | Required | Role |
|---|---|---|
| `of` | Required | Name of the array attribute on the current row to unwind. Must be an array type (`object[]` / `string[]` / `integer[]` / ...). |
| `as` | Optional | Name given to the element on each produced row. Defaults to the value of `of:`. |
| `preserve_empty` | Optional | `true` keeps parent rows whose array is empty or missing (the `as:` field is absent on those rows). Default `false` drops them. |

The shorthand `flatten: <name>` is equivalent to `flatten: { of: <name>, as: <name>, preserve_empty: false }`.

### Output shape

For `from: categories` + `flatten: { of: tasks, as: task }`, given input:

```yaml
categories:
  - id: A
    tasks:
      - { id: A1, phase: 8 }
      - { id: A2, phase: 10 }
  - id: B
    tasks:
      - { id: B1, phase: 10 }
```

the intermediate result after `flatten` (before `where`):

```yaml
- { id: A, task: { id: A1, phase: 8 } }
- { id: A, task: { id: A2, phase: 10 } }
- { id: B, task: { id: B1, phase: 10 } }
```

Parent fields (e.g. `id`) stay at the top level; element fields are accessed via the `as:` namespace (`row.task.id`).

### When the array is empty

When N = 0 (the array at `of:` resolves to `[]` or the attribute is absent), an input row by default produces no output rows — the parent is dropped. Setting `preserve_empty: true` makes such rows survive as a single output row with no `as:` field, useful when the template needs to emit an entry for every parent regardless of whether children exist.

## where

Filters records by a predicate. Top-level keys are field names or the combinators `and` / `or` / `not`; multiple keys at the same level combine by implicit AND.

```yaml
where:
  active: true                  # field: scalar is shorthand for { eq: <scalar> }
  age: { gt: 10, lt: 20 }       # multi-predicate bundle combines by AND
  or:
    - role: engineer
    - role: designer
  not:
    id: { startswith: '__' }
```

### Operators

The closed set of atomic operators:

| Operator | Target type | Meaning |
|---|---|---|
| `eq` | any scalar | Equality. The type matters — `42` and `"42"` are not equal. |
| `gt` / `gte` / `lt` / `lte` | number | Numeric comparison. The record value must also be numeric (`int` / `float`, excluding `bool`); other types fail to match silently. |
| `startswith` / `endswith` / `contains` | string | String prefix / suffix / substring. Non-string record values fail to match silently. |
| `exists` | boolean | `true` requires the field to be present in the record; `false` requires it absent. |

`eq` accepts a bare scalar value as shorthand (`field: <scalar>` is equivalent to `field: { eq: <scalar> }`).

### Combinators

| Combinator | Argument | Meaning |
|---|---|---|
| `and` | list of clauses | All clauses must match. |
| `or` | list of clauses | At least one clause must match. |
| `not` | single clause | The inner clause must NOT match. |

Multiple keys at the same level — fields, combinators, or both — combine by implicit AND.

## grouped

Groups an array of objects by a specified field. The result is an array; each element holds the group key's value and an inner array of the group's members.

```yaml
grouped:
  by: role               # field used to group
  as: members            # name of the inner array (defaults to the last segment of from)
```

| Key | Required | Role |
|---|---|---|
| `by` | Required | Name of the field used as the grouping key. |
| `as` | Optional | Name given to the inner array of group members. Defaults to the last segment of `from:`. |

Group order follows the source data's order (the order in which each key first appears). Records within a group keep the source's shape, including the grouping field.

### Output shape

For `from: members` + `grouped: { by: role }`, given input:

```yaml
members:
  - { id: alice, name: Alice, role: engineer }
  - { id: bob,   name: Bob,   role: engineer }
  - { id: carol, name: Carol, role: designer }
```

the intermediate result after `grouped` (before `select`):

```yaml
- role: engineer
  members:                             # `as` omitted, so the inner-array name is the last segment of from: "members"
    - { id: alice, name: Alice, role: engineer }
    - { id: bob,   name: Bob,   role: engineer }
- role: designer
  members:
    - { id: carol, name: Carol, role: designer }
```

## select

Lists the fields to include in the output. When omitted, the result is an array of empty objects.

```yaml
select:
  - item: role
    as: id              # emit the role value under the field name id
  - item: role          # emit role as-is
  - item: members       # emit the array named by grouped.as
```

| Key | Required | Role |
|---|---|---|
| `item` | Required | Name of the field to read from the input record. |
| `as` | Optional | Field name in the output. Defaults to the value of `item` when omitted. |

Fields not listed in `select` are excluded from the output. The grouping field and the inner array generated by `grouped` are also omitted unless explicitly listed in `select`.

## sort

Orders the final output records by one field. Runs after `select`, so `by:` references attribute names in the projected output (including any `as:` aliases).

```yaml
sort:
  by: phase              # required
  direction: desc        # asc (default) / desc
  missing: last          # first / last (default: last)
```

| Key | Required | Role |
|---|---|---|
| `by` | Required | Name of the output field to order by. |
| `direction` | Optional | `asc` (default) or `desc`. |
| `missing` | Optional | `first` or `last` (default). Where to place records that lack the `by:` field. |

### Missing-key placement

`missing:` is **independent of `direction:`**. `missing: first` always places records whose sort key is absent at the head; `missing: last` (the default) always places them at the tail — regardless of `asc` / `desc`.

For `from: members` with three records `[{name: alice, age: 30}, {name: bob}, {name: carol, age: 25}]` and the following sort clauses:

| sort | result order (names) |
|---|---|
| `{by: age}` | carol, alice, bob (missing at end) |
| `{by: age, direction: desc}` | alice, carol, bob (missing still at end) |
| `{by: age, missing: first}` | bob, carol, alice |
| `{by: age, direction: desc, missing: first}` | bob, alice, carol |

## Inspecting a view

Each query's result is exposed via an auto-generated meta page at `output/__meta_query/<query>.md`. While writing a query, you can verify the result in real time on `mood watch`.

## Full query-schema

The built-in schema that constrains the form of query files. The canonical specification is the YAML at [`./schemas/query-schema.yaml`](./schemas/query-schema.yaml).
