# Reports

The **reports** file configures report output. It lives at `{project}/definition/reports.yaml` and is required — every project must have it. `mood init` and every blueprint produce a starter copy.

```yaml
# definition/reports.yaml
file_per:
  - erds.item
  - erds.item.entities.item
```

`file_per:` lists the ObjectType IDs whose nodes are split out as separate files (read as "one file per ObjectType instance"). A node whose type is not listed expands inline instead; an empty list (or an omitted `file_per:`) inlines everything into a single `index.md`. See [Template — Split vs inline](template.md#split-vs-inline) for how a subtemplate chooses between the two.

## Schema

The built-in meta-schema is mirrored at [schemas/reports-schema.yaml](schemas/reports-schema.yaml) for direct reference.

A split page is written at its **anchor-derived path** under the report root: the directory follows the view the node came from and the filename is the record's `id` (so a record from the `erds` view lands at `reports/erds/{id}.md`). See [Template — Output path](template.md#output-path).
