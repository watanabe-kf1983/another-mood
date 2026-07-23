# Manifest

The **manifest** declares what a project is: its display title and the format generation its sources follow. It lives at `{project}/sbdb.yaml` ("sbdb": source-based database) — directly in the project directory, next to `definition/` and `contents/`.

```yaml
# sbdb.yaml
sbdb_version: 1
title: My Project
tools:
  another-mood:
    minimum_version: "0.1.0"
```

`mood init` and `mood blueprint apply` generate this file — titled after the project directory, with `minimum_version` set to the Another Mood that generated it; edit `title` to taste.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `sbdb_version` | yes | Format generation these sources follow. Integer. Currently `1`. |
| `title` | no | Project display name, shown on the top page. Defaults to the project directory name. |
| `tools.another-mood.minimum_version` | no | Minimum Another Mood version this project requires — a floor the sources are known to work at. |

Both version fields are checked at the start of every build.

## Schema

The schema is mirrored at [schemas/manifest-schema.yaml](schemas/manifest-schema.yaml) for direct reference.
