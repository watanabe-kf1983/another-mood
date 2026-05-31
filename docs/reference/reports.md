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

## Status

Validation and parsing of `reports.yaml` are wired into the build today. The file-splitting behaviour itself is being landed incrementally; until it is fully wired, `file_per:` is recorded but does not yet drive how the output is split.
