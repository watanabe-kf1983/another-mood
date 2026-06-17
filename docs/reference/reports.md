# Reports

The **reports** file configures report output. It lives at `{project}/definition/reports.yaml` and is required — every project must have it. `mood init` and every blueprint produce a starter copy.

```yaml
# definition/reports.yaml
file_per:
  - erds.item
  - erds.item.entities.item
```

`file_per:` lists the **type IDs** whose nodes are split out as separate files. A node whose type is not listed expands inline instead; an empty list (or an omitted `file_per:`) inlines everything into a single `index.md`. See [Template — Split vs inline](template.md#split-vs-inline) for how a subtemplate chooses between the two, and [Type IDs](#type-ids) below for the values to list here.

## Type IDs

A **type ID** names a type in the schema — the value you list under `file_per:`. Two forms cover the usual list-and-detail layout:

- `X.item` — **each record** of a type (e.g. `members.item`): one detail page per record (`reports/members/alice.md`).
- `X.item[]` — the **collection** of those records (e.g. `members.item[]`): one list page for the whole collection (`reports/members.md`). It is the record form with `[]` appended — the array *of* `X.item`.

So a member list plus per-member detail pages is `file_per: [members.item[], members.item]`. Nesting extends the path one level per array — each task within a category is `categories.item.tasks.item`, and that task list is `categories.item.tasks.item[]`.

To find the exact values, read the diagnostics. `output/__entity_defs/{entity}.md` shows each record type as a `Type:` heading and each array field's collection type in the attributes table; `output/__queries/{query}.md` does the same for query result shapes. Copy the value verbatim.

## Schema

The built-in meta-schema is mirrored at [schemas/reports-schema.yaml](schemas/reports-schema.yaml) for direct reference.

A split page is written at its **anchor-derived path** under the report root: the directory follows the view the node came from and the filename is the record's `id` (so a record from the `erds` view lands at `reports/erds/{id}.md`). See [Template — Output path](template.md#output-path).
