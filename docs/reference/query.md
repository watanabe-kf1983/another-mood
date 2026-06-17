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
| `join` | Optional | Attach one or more related entities. |
| `where` | Optional | Per-record filter applied before grouping. |
| `grouped` | Optional | Grouping of records. |
| `select` | Optional | Projection of output fields. When omitted, records pass through unchanged. |
| `sort` | Optional | Ordering of the final output records. |

Evaluation order: `from` → `flatten` → `join` → `where` → `grouped` → `select` → `sort`.

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
from: artists
flatten: members                   # 1 row per member; element placed under `members`

# Single attribute, object form
from: artists
flatten:
  of: members
  as: member                       # rename the element namespace
  preserve_empty: true             # keep artists whose member map is empty or missing

# Multiple attributes, list form (each later entry sees the row shape
# produced by earlier ones). The example imagines `artists` carries
# additional `tours` and `awards` arrays alongside `members`:
from: artists
flatten:
  - tours
  - { of: awards, as: award }
```

| Key | Required | Role |
|---|---|---|
| `of` | Required | Name of the array attribute on the current row to unwind. Must be an array type (`object[]` / `string[]` / `integer[]` / ...). |
| `as` | Optional | Name given to the element on each produced row. Defaults to the value of `of:`. |
| `preserve_empty` | Optional | `true` keeps parent rows whose array is empty or missing (the `as:` field is absent on those rows). Default `false` drops them. |

The shorthand `flatten: <name>` is equivalent to `flatten: { of: <name>, as: <name>, preserve_empty: false }`.

### Output shape

For `from: artists` + `flatten: { of: members, as: member }`, given input:

```yaml
artists:
  - id: A
    members:
      - { id: m1, name: Anna, instrument: synth  }
      - { id: m2, name: Beth, instrument: drums  }
  - id: B
    members:
      - { id: m3, name: Carl, instrument: vocals }
```

the intermediate result after `flatten` (before `where`):

```yaml
- { id: A, member: { id: m1, name: Anna, instrument: synth  } }
- { id: A, member: { id: m2, name: Beth, instrument: drums  } }
- { id: B, member: { id: m3, name: Carl, instrument: vocals } }
```

Parent fields (e.g. `id`) stay at the top level; element fields are accessed via the `as:` namespace (`row.member.id`).

### When the array is empty

When N = 0 (the array at `of:` resolves to `[]` or the attribute is absent), an input row by default produces no output rows — the parent is dropped. Setting `preserve_empty: true` makes such rows survive as a single output row with no `as:` field, useful when the template needs to emit an entry for every parent regardless of whether children exist.

## join

For each input row, looks up matching rows in another entity and attaches them. "Matching" is defined by single key equality: one attribute on the current row equals one attribute on the other entity's row.

Throughout this section the examples assume two source entities:

```yaml
artists:
  - { id: A, name: Apricot }
  - { id: B, name: Birch }
  - { id: Z, name: Zephyr }   # no matching album

albums:
  - { id: D1, artist_id: A, is_live: false }
  - { id: D2, artist_id: A, is_live: true  }
  - { id: D3, artist_id: B, is_live: false }
```

### Default: attach matches as a list

Without an inline `flatten:` (introduced below), each input row produces exactly one output row — the matches arrive together as a list under `as:`.

```yaml
from: artists
join:
  to: albums
  on: { left: id, right: artist_id }
```

Intermediate result after `join` (before `where`):

```yaml
- { id: A, name: Apricot, albums: [{id: D1, artist_id: A, ...}, {id: D2, artist_id: A, ...}] }
- { id: B, name: Birch,   albums: [{id: D3, artist_id: B, ...}] }
- { id: Z, name: Zephyr,  albums: [] }    # no match — kept with an empty list
```

The list lives under the join's `as:`, which defaults to `to:` (here `albums`). Set `as:` explicitly to avoid collisions with existing attributes or to disambiguate multiple joins to the same entity.

### Inline `flatten:` — one row per match

Adding an inline `flatten:` unwinds the attached list in place: one output row per (input, match) pair.

```yaml
from: artists
join:
  to: albums
  on: { left: id, right: artist_id }
  flatten: { as: album }   # rename: plural `albums` → singular `album`
```

Intermediate result:

```yaml
- { id: A, name: Apricot, album: {id: D1, artist_id: A, ...} }
- { id: A, name: Apricot, album: {id: D2, artist_id: A, ...} }
- { id: B, name: Birch,   album: {id: D3, artist_id: B, ...} }
```

`Z` has no matching album, so no row is produced for it. To keep input rows with no match, add `preserve_empty: true`:

```yaml
join:
  to: albums
  on: { left: id, right: artist_id }
  flatten: { as: album, preserve_empty: true }
```

```yaml
- { id: A, name: Apricot, album: {id: D1, artist_id: A, ...} }
- { id: A, name: Apricot, album: {id: D2, artist_id: A, ...} }
- { id: B, name: Birch,   album: {id: D3, artist_id: B, ...} }
- { id: Z, name: Zephyr }                # surviving row carries no `album` field
```

For readers familiar with SQL: the no-`flatten:` form (matches as a list) has no direct SQL analogue; default `flatten:` is the `INNER JOIN` shape; and `preserve_empty: true` is the `LEFT JOIN` shape.

The shorthand `flatten: true` stands for the all-defaults form `flatten: {}` — no rename (so the slot keeps the join's plural `as:` name) and `preserve_empty: false`.

### Fields

| Key | Required | Role |
|---|---|---|
| `to` | Required | Id of the entity to match against. |
| `on` | Required | `{ left, right }` — match rows where the input row's `left:` attribute equals the other entity's `right:` attribute. |
| `as` | Optional | Name given to the matches on each output row. Defaults to the value of `to:`. |
| `where` | Optional | Pre-join filter applied to `to:` before matching. Same grammar as the top-level `where:`. |
| `flatten` | Optional | Unwind the attached list in place. `true` for shorthand, or an object with `as:` (defaults to the join's `as:`) and `preserve_empty:` (defaults to `false`). |

`on.left:` and `on.right:` accept a dotted path through a nested singleton object (e.g. `meta.kind`), but cannot cross a list. Only the top-level `flatten:` and the inline `flatten:` here change row cardinality — other clauses always operate within a single row's attributes and never reach into a nested list.

### Pre-join `where:` (and the SQL LEFT-WHERE trap)

A `where:` written *inside* the join filters `to:` **before** the match runs. The top-level `where:` (outside the join) runs **after**. The distinction matters when input rows with no match must survive — i.e. when `flatten: { preserve_empty: true }` is set:

```yaml
# Right: filter the albums first; artists with no surviving album still appear.
from: artists
join:
  to: albums
  on: { left: id, right: artist_id }
  where:
    is_live: false            # pre-join filter
  flatten:
    as: album
    preserve_empty: true

# Wrong: filtering on the joined attribute at the top level silently
# drops the artists whose only album was a live one (and the artists
# with no album at all), turning the LEFT-shape into an INNER-shape.
# The classic SQL gotcha.
from: artists
join:
  to: albums
  on: { left: id, right: artist_id }
  flatten:
    as: album
    preserve_empty: true
where:
  album.is_live: false        # post-join filter
```

With the source data above, the **right** form yields:

```yaml
- { id: A, name: Apricot, album: {id: D1, is_live: false, ...} }   # D2 dropped: is_live=true
- { id: B, name: Birch,   album: {id: D3, is_live: false, ...} }
- { id: Z, name: Zephyr }                                            # kept: preserve_empty
```

The wrong form additionally drops `Z` — its row has no `album` field, so `album.is_live: false` cannot hold and the post-join `where:` removes it.

### Multiple joins (list form)

Several joins are written as an ordered list. Each later item sees the row shape produced by earlier ones — so a later `on.left:` can reference an attribute introduced by an earlier `flatten.as:`.

Suppose each album additionally carries a `label_id:` reference, and a separate `labels` entity describes those:

```yaml
albums:
  - { id: D1, artist_id: A, label_id: L1 }
  - { id: D2, artist_id: A, label_id: L1 }
  - { id: D3, artist_id: B, label_id: L2 }

labels:
  - { id: L1, name: Amber Records }
  - { id: L2, name: Iron Pulse }
```

A two-stage join attaches each album and then, for each album, the album's label:

```yaml
from: artists
join:
  - to: albums
    on: { left: id, right: artist_id }
    flatten: { as: album }                  # 1 row per (artist, album)
  - to: labels
    on: { left: album.label_id, right: id } # `album.label_id` from prior flatten
    flatten: { as: label }                  # 1 row per (artist, album, label)
```

If the earlier join had no inline `flatten:`, its `as:` would still be a list at the next step; a later `on.left:` cannot reach inside a list (only `flatten:` ever traverses one), so the unwind must come first.

The single-object form (`join: { to: ..., on: ... }`) is equivalent to a 1-element list — a shorthand for the common one-join case.

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
  members:                # `as` omitted - default = last segment of `from:` ("members")
    - { id: alice, name: Alice, role: engineer }
    - { id: bob,   name: Bob,   role: engineer }
- role: designer
  members:
    - { id: carol, name: Carol, role: designer }
```

## select

Lists the fields to include in the output. When omitted, records pass through unchanged (all fields preserved).

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

If a listed `item:` is absent on a particular record (the source attribute is schema-optional and the record omits the value), the output row simply omits that key. No error is raised and no null is invented — consistent with the data model's "nullable = absent key" convention.

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

Each query's result is exposed via an auto-generated meta page at `output/__queries/<query>.md`. While writing a query, you can verify the result in real time on `mood watch`.

## Full query-schema

The built-in schema that constrains the form of query files. The canonical specification is the YAML at [`./schemas/query-schema.yaml`](./schemas/query-schema.yaml).
