# Pipeline

The pipeline that generates the final documents from the user's definition and contents.

## Stages

| Stage | User Input | Upstream | Output |
|---|---|---|---|
| inspect_schema | schema_file | — | inspect_schema/ |
| normalize_contents | contents_dir | inspect_schema/ | normalize_contents/ |
| derive_queries | views_dir | inspect_schema/ | derive_queries/ |
| compose | — | normalize_contents/, derive_queries/ | compose/ |
| generate | templates_dir, reports_file | compose/ | generate/ |
| reconcile | — | generate/ | reconcile/ |
| site | — | reconcile/ | prepare_site/, hugo_build/ |
| publish | — | hugo_build/ | out_dir (the content of reconcile/), site_dir (the content of hugo_build/) |
| tap | — | compose/ | tap/ |
| tap_schema | — | derive_queries/ | tap_schema/ |

Output is the directory named after the component, directly under the working directory (`Workspace.root`). The site stage runs two components, prepare_site and hugo_build, so it has two outputs.

publish copies reconcile/ too, but watches only the final hugo_build/, because by the time that has completed, every earlier stage has settled (`publish_stage` in `pipeline/stages.py`).

normalize_contents reads schema_file too but does not watch it. A schema change arrives as an update of inspect_schema/ ([Data catalog](30-communication/20-data-catalog.md)).

`mood tap` and `mood tap --schema` share the same sequence of stages partway, differing only at the end (`TAP_STAGE_FACTORIES` / `TAP_SCHEMA_STAGE_FACTORIES` in `pipeline/stages.py`):

- `mood tap` — shares up to compose, and ends with tap (compose/ → tap/)
- `mood tap --schema` — shares up to derive_queries, and ends with tap_schema (derive_queries/ → tap_schema/)

Neither has publish; the command layer reads the document and returns it.

In watch, changes to User Input / Upstream are watched and the stage reruns automatically (see `pipeline/base.py`). In build, the stages run serially in dependency order. Upstream is the Output of the preceding stage, and the place `BuildReport` (error propagation) is collected from.

## The watch library is watchdog

[watchdog](https://github.com/gorakhargosh/watchdog) is used. The earlier watchfiles switched to forced polling whenever it detected WSL, even on WSL2, and the dropped events brought watch to a halt.
