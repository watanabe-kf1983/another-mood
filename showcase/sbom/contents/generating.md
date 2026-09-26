# Generating the SBOM

`sbom.json` is a snapshot of the packages Another Mood installs at runtime, taken once with the steps below. It is sample data, not a live ledger: it does not follow later dependency changes. To refresh it, run the steps again.

The same steps work for any Python project managed with [uv](https://docs.astral.sh/uv/). Run them from the project root.

## 1. Install the runtime dependencies into a throwaway environment

```sh
UV_PROJECT_ENVIRONMENT=/tmp/sbom-venv uv sync --no-dev --frozen
```

`--no-dev` leaves out test and lint tools, so the SBOM answers one question: what ships with the package.

## 2. Generate a CycloneDX SBOM from that environment

```sh
uvx --from cyclonedx-bom cyclonedx-py environment \
  --output-reproducible --pyproject pyproject.toml \
  -o /tmp/sbom.json /tmp/sbom-venv/bin/python
```

- `--output-reproducible` drops the timestamp and serial number, so regenerating an unchanged environment gives an identical file.
- `--pyproject` records the project itself as the root component.

## 3. Reshape it with jq

```sh
jq '{root_component: .metadata.component, components, dependencies}
  | walk(if type == "object" and has("bom-ref")
         then {ref: .["bom-ref"]} + del(.["bom-ref"]) else . end)' \
  /tmp/sbom.json > contents/sbom.json
```

The generator's output does not fit the schema language as-is, for two reasons, and this step fixes only those:

- **The envelope.** Top-level keys such as `$schema`, `bomFormat` and `specVersion`, and the generator's own entry under `metadata.tools`, describe the file rather than the software. The step keeps `components` and `dependencies`, and lifts the root component out of `metadata`.
- **A key that is not an identifier.** Property names in `definition/schema.yaml` must be identifiers, so `bom-ref` becomes `ref`.

Everything else, including the three shapes a license can take, is left exactly as the generator wrote it. Reading it into the shapes the pages need is the job of the views in `definition/views/`.
