# View

Behavior kept on purpose, outside the contract of `docs/reference/view.md`. The stage names in this chapter (`derive_queries`, `compose`, `generate`) are those of the [stage table of the internal structure](../20-internal/20-pipeline.md#stages).

Terms used in this chapter:

- **view** — a named set of records derived by a query. Templates read it in the same namespace as entities (Template context in `docs/reference/template.md`)
- **row** — one record passed from clause to clause in a query
- **database pages** — the pages under `__db/` that the tool draws automatically from the schema and view definitions. `__db/__defs/` holds the definitions (entities and views), `__db/__data/` their actual data. In the cover's section name, Database Information
- **clause pipeline** — the flow within one query in which clauses pass rows along in a fixed order. Distinct from the [Pipeline](../20-internal/20-pipeline.md) of the internal structure, which is the sequence of stages
- **`__definition.views`** — the list of view definitions. Part of the self-description of the [data catalog](../20-internal/30-communication/20-data-catalog.md), from which the database pages draw the list of views

## Clause pipeline

### Clause order is fixed; a shape that does not fit is split into another view and referenced by name

Clauses are evaluated in a fixed order (Evaluation order in `docs/reference/view.md`). A shape that does not fit this order (narrowing with `where` before `flatten`, joining the result of `grouped`, and so on) is handled by cutting the earlier step out into another view and connecting to it by writing its name in `from:` or `join.to:`.

Inline subqueries, nesting a query inside `from:`, are not adopted. Reasons:

- The result of a named view is written to a file of its own (`view-results/` in `compose`'s output) and can be checked step by step. The inside of a nested query would be the one place where an intermediate result is not materialized
- A shared earlier step (such as a pair of flatten and join) can be written once
- The standard answer to "I want clause X at position Y too" becomes "split", which holds back the proliferation of clauses and ordering options
- The ergonomics of writing recursive structures in YAML are worse than SQL's parentheses

All views are evaluated once at build time in a deterministic order and their results materialized, so the opacity of execution plans when views are stacked in an RDBMS does not exist here. A view reference is closer to an intermediate variable in a script than to an RDBMS view.

The evaluation order follows the reference relations, not the order of files. The order of `__definition.views`, on the other hand, is kept as the file path order and the order within files, and the evaluation order is not shown to the user.

A split-out intermediate view is visible to templates and the database pages like any other view. There is no mechanism to hide it.

Placing `sort` after `select` in the fixed order (`sort.by` names the projected names) follows the order that SQL (`SELECT` → `ORDER BY`), MongoDB aggregation, PRQL, pandas, and LINQ all share.

### Arrays the source already has are opened by the top-level `flatten:`; arrays a join made are opened by the `flatten:` inside that join

The top-level `flatten:` opens only arrays the source records already have (nested collections, arrays of scalars). The array a join attaches at `as:` is not a target of the top level; write `flatten:` inside that join to open it.

Opening an array the source already has is a statement about how the persisted data is read, tied to the shape of the data. A join's array is a shape the query made temporarily, and keeping its adjustment inside the clause that made it puts cause and fix in the same place.

The same stance is behind the contract's rule that "the only clause that reaches an array inside a row is flatten". The verbs that touch arrays are gathered into flatten alone, and the other clauses look only at a row's attributes.

So no clause is added for shapes such as filtering the parent by the array's content, or sorting within the array. Open the array into rows with flatten, then apply `where` or `sort`, and if needed bundle again with `grouped` or join's default form (attaching the list as is).

### A flattened row keeps the parent's attributes and puts the element under `as:`

The form that promotes the element's attributes to the top of the row and discards the parent's information is not adopted.

- The parent's attributes can be read from the row as they are, so no mechanism to climb back to the parent row is needed
- Even when flatten and join are stacked, collisions are avoided by namespace
- The meaning of `as:` is the same "namespace prefix" in join's default form (the name of the array) and after flatten (the name of the one element)

## Writing clauses

### `as:` can be omitted in clauses where what it names is written in the same mapping, and is required where it is not

What `flatten.as` / `join.as` / `select.as` name is exactly what `of:` / `to:` / `item:` in the same mapping point at, so using that name as the default does not stray from the meaning. What `grouped.as` names is the list of the group's rows, and `by:` is the key that bundles those rows, not the name of the list, so there is no name to borrow.

### `where` has no `neq`; negation is gathered into `not`

In the data model, the absence of a value is expressed by omitting the key ([JSON data model](../20-internal/30-communication/10-json-data-model.md)). With `neq`, there are three readings of how a record with the key missing is treated, and the answers diverge:

- Read as ≠ on actual data, true (there is no value, so it differs from x)
- Read as SQL's three-valued logic, UNKNOWN, so it drops out of `where`
- Read as the negation of `eq`, true (`eq` is false, so inverted, true)

Whichever is chosen looks unnatural to a user who expected another reading.

Instead, two rules fix the meaning. An atomic predicate is always false on a missing key (except `exists`), and `not` inverts the result inside it. "Not equal" is written `not: { field: x }`, and rows with the key missing remain. The behavior of negation is concentrated in one place, `not`, and need not be considered per predicate.

### A missing key in `sort` is placed by `missing:`, independent of `direction`, last by default

The word is `missing`, not `null`. The data model has no notion of a null value, and `where` expresses the existence test as `exists`, so borrowing SQL's `NULLS FIRST/LAST` here alone would make the vocabulary uneven. Same as Elasticsearch's `missing: _first/_last`.

The position is given by a parameter independent of `direction` (the PostgreSQL and pandas way). The MySQL and MongoDB way, which pins null as the largest or smallest value and derives the position from the direction, assumes "null is a kind of value", which does not fit the data model.

The default is last regardless of direction, because "missing keys go last" holds for `asc` and `desc` alike, and the user need not remember "what rank is null as a value".

### A dot means nesting, and no key with a dot in it appears in the output

Names in the DSL are paths, for reading and writing alike, and a dot expresses nesting. The reading names (`from`, `flatten.of`, `on`, the keys of `where`, `grouped.by`, `select.item`, `sort.by`) walk nested objects.

If a writing name (`flatten.as`, `join.as`, `select.as`, `grouped.as`, the write-back of `grouped.by`, a view name) has a dot, the output is nested at that position, and intermediate objects are created if absent. For a view name, that object also stands in the catalog as an attribute of the root (Nested views in `docs/reference/view.md`).

The rule when writes overlap is the same as MongoDB's projection and TOML's dotted keys:

- Writes to siblings (`a.b` and `a.c`) merge into one object
- Writes where one is a prefix of the other (`a` and `a.c`) are an error. Seen per segment, so `hobby` and `hobbyist` do not overlap

Collisions between view names, and between a view name and a top-level data entity, are judged by this rule too.

## Database pages

### A view's definition page shows, next to the definition, the shape that follows from it

`__db/__defs/views/<view>` shows a **Shape** below the query's definition (Diagnostics in `docs/reference/view.md`). The Shape is a table of each output attribute's type and its x-ref target (a reference to a record of another entity; [Schema](30-schema.md#x-ref)).

Conveying the shape is not left to the column headings and rows of the data page (`__db/__data/views/<view>`) alone.

Records in this tool can have composite types (object / object[]), so guessing the shape from values goes wrong.

Whether a `tasks` column is an array of strings or an array of records of the nested entity `categories.tasks` cannot be read from a row with an empty array or a row where it is missing. SQL clients can omit the type display because every column is assumed to be a scalar.

It is placed on the definition page rather than the data page to match the structure of the entity definition page `__db/__defs/entities/<entity>`. That page puts the schema definition next to a table of the types the tool read from it. Both read "the definition, and the types that follow from it" on one page.

The Shape is drawn from the catalog without looking at the data. That a view's shape is determined independently of the data is in [Data catalog](../20-internal/30-communication/20-data-catalog.md#composes-output-matches-the-shape-the-catalog-declares).
