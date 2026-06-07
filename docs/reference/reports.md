# Reports

The **reports** file configures report output. It lives at `{project}/definition/reports.yaml` and is required — every project must have it. `mood init` and every blueprint produce a starter copy.

```yaml
# definition/reports.yaml
file_per:
  - erds.item
  - erds.item.entities.item
```

`file_per:` lists the ObjectType IDs whose nodes will be split out as separate files (read as "one file per ObjectType instance"). An empty list (or an omitted `file_per:`) means "no splitting — everything inlines into a single `index.md`".

## Schema

The built-in meta-schema is mirrored at [schemas/reports-schema.yaml](schemas/reports-schema.yaml) for direct reference.

A split page is written at its **anchor-derived path** under the report root: the directory follows the view the node came from and the filename is the record's `id` (so a record from the `erds` view lands at `reports/erds/{id}.md`). See [Template — Automatic output path](template.md#automatic-output-path).

## Status

Validation and parsing of `reports.yaml` are wired into the build, and `file_per:` now drives **where** a split page is written (its anchor-derived path). The remaining piece is the automatic split-vs-inline decision: today a `{% mood_view %}` splits unless marked `inline`, so an ObjectType you split must appear in `file_per:`. Folding the split/inline choice onto `file_per:` itself — so an unlisted node inlines automatically — is still being landed.
