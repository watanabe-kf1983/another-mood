# Pipeline

The pipeline that generates the final documents from the user's definition and contents.

## Stages

The stages of `mood watch`, the mode this arrangement exists for:

| Stage | User Input | Upstream | Output |
|---|---|---|---|
| inspect_schema | schema_file | — | inspect_schema/ |
| normalize_contents | contents_dir | inspect_schema/ | normalize_contents/ |
| derive_queries | views_dir | inspect_schema/ | derive_queries/ |
| compose | — | normalize_contents/, derive_queries/ | compose/ |
| generate | templates_dir, reports_file | compose/ | generate/ |
| reconcile | — | generate/ | reconcile/ |
| site | — | reconcile/ | prepare_site/ (served by the Hugo server) |

Output is the directory named after the component, directly under the working directory (`Workspace.root`).

Changes to User Input / Upstream are watched and the stage reruns automatically (see `pipeline/base.py`). Upstream is the Output of the preceding stage, and the place `BuildReport` (error propagation) is collected from.

normalize_contents reads schema_file too but does not watch it. A schema change arrives as an update of inspect_schema/ ([Data catalog](30-communication/20-data-catalog.md)).

Other commands run variations of this sequence. `mood build` runs the stages once each in dependency order, builds prepare_site/ into HTML with hugo_build instead of serving it, and ends with publish, which copies reconcile/ and hugo_build/ to out_dir and site_dir. `mood tap` stops before rendering. The exact stage lists are the `*_STAGE_FACTORIES` in `pipeline/stages.py`.

## The watch library is watchdog

[watchdog](https://github.com/gorakhargosh/watchdog) is used. The earlier watchfiles switched to forced polling whenever it detected WSL, even on WSL2, and the dropped events brought watch to a halt.
