# Architecture

## Layers

- **Entry point (`cli`)**: input and output with the user. Holds no operations itself
- **command**: one command, one function. Returns the result as a value and leaves display on the terminal to the entry point
- **pipeline**: arranges the components into stages, and runs them once for build and on every input change for watch. The contact with external tools (Hugo, watchdog) is here too
- **components**: business logic. Functions from an input directory to an output directory, knowing neither each other nor the pipeline
- **components/shared**: the foundation shared by the components

## The three things received at startup

Before one run, command reads three things of different nature, separately:

- **Config** (`ProjectConfig` in `config.py`) — what the operator hands over at startup. How to run and where to write (the output destination, the port, and so on), and the injected values `vars` delivered to templates (Injected values in `docs/reference/cli.md`). CLI arguments are interpreted by the CLI and passed in; environment variables are read by the config side directly
- **Manifest** (`components/manifest`) — what the project is. Reads `sbdb.yaml` and passes the generation and minimum version checks
- **Layout** (`SourceLayout` in `layout.py`) — the paths of the sources. Derived from `project_dir`, and their existence verified. If the layout changes per generation, the branch goes here

The three are not mixed. Config has no field that moves the location of sources, and the manifest has no build settings. Config only carries `vars` and does not read their content. The user-visible reasons are in the external design's [Manifest](../10-external/20-manifest.md#location-and-role) and [CLI](../10-external/10-cli.md#locations).

The config is assembled first by the CLI and passed to command. command reads the manifest, then the layout, and then starts the pipeline. The layout is a contract surface too, and may differ by generation, so checking the layout is meaningful only after the generation check has passed. An unsupported generation is reported before "sources missing" (`build` in `command.py`).

## How build and watch are served by the same components

A component is a function that "reads this directory and writes that directory", unaware of whether it is run once or continuously. A **stage** is the unit of execution in which the pipeline binds one component to the input paths it watches (the user's input files and the output directory of the immediately upstream stage) and its output directory.

build runs the stages once each in dependency order; in watch, each stage waits for changes on its own watched paths and reruns:

```
user input ─▶ Stage A ─▶ A/ ─▶ Stage B ─▶ B/ ─▶ ...
  (A watches)            (B watches)
```

In watch, when an upstream stage rewrites its output, the downstream runs by itself, so there is no need to manage the order of reruns centrally, and changes propagate from upstream to downstream.

For this to hold, each stage's output directory must be updated atomically, with no intermediate state visible downstream. This invariant, and the shape of the data flowing between stages ([JSON data model](30-communication/10-json-data-model.md), [transport of blobs](30-communication/index.md#hand-over-between-stages-is-by-hardlink)), are written in [Inter-Stage Communication](30-communication/index.md).

A stage is never interrupted by an error. An exception raised inside a component's processing is converted by the shared foundation (`error_propagation`, with which `Component` wraps the function) into part of the output (`BuildReport`) and propagated downstream. How the report travels is in [Inter-Stage Communication](30-communication/index.md#error-propagation-buildreport).

The list of stages and their inputs and outputs has its source of truth in the stage table of [Pipeline](20-pipeline.md).

## Components

For each component: the stage it runs, where the code is, and what it is responsible for. The list of stages is in [Pipeline](20-pipeline.md).

## SchemaInspector

`inspect_schema` — `components/preprocess/schema_inspector.py`

Validates the schema definition against the meta-schema and extracts the [data catalog](30-communication/20-data-catalog.md) (the inventory of entities and attributes built from the schema; downstream stages read it instead of the schema). The behavior kept on purpose is in the external design's [Schema](../10-external/30-schema.md).

## Content Normalizer

`normalize_contents` — `components/preprocess/content_normalizer.py`

Validates every file in `contents/`, normalizes them, merges them into one data tree, and checks x-refs and ids. For blobs, it mirrors the bytes, separately from the records, into its own output, and generate copies them again into each edition's output ([a blob's anchor path](30-communication/index.md#a-blobs-anchor-path-is-also-its-output-address)). The behavior kept on purpose is in the external design's [Schema](../10-external/30-schema.md).

## Query Deriver

`derive_queries` — `components/preprocess/query_deriver.py`

Validates and normalizes the views input, parses each view definition, and generates the derived entities (`view: true`) from the catalog. The output is the whole catalog: the data catalog with the views added as attributes of the root, plus the view definitions and derived entities. The behavior kept on purpose is in the external design's [View](../10-external/40-view.md).

## Composer

`compose` — `components/composer/composer.py`

Passes the normalized data and the catalog through as they are, and evaluates the view definitions in reference order. Each view's result is also added to the sources of the next view. The behavior kept on purpose is in the external design's [View](../10-external/40-view.md).

## Tap

`tap` — `components/tap/tap.py`

Merges compose's output into one JSON document. **Tap Schema** (`tap_schema`; `components/tap/tap_schema.py`) writes out the JSON Schema of that document from derive_queries' catalog. The behavior kept on purpose is in the external design's [CLI](../10-external/10-cli.md).

## Document Generator

`generate` — `components/generator/generator.py`

Repacks compose's output into an inert tree, attaches an address (anchor path) and type metadata to each node (`generator/data_tree.py`), and draws Markdown pages with the templates per edition. The cover and the database pages under `__db/` are drawn here too.

The behavior kept on purpose is in the external design's [Template](../10-external/50-template.md), [Reports](../10-external/60-reports.md), and [Trust Model](../10-external/70-trust-model.md).

## Reconcile

`reconcile` — `components/generator/generator.py`

Matches the Generator's output against the `BuildReport` propagated from upstream, and settles the final output shown to the user.

With no errors, it adds the colophon page (`__build_info/`) and the warnings page (`__warnings/`) to the Generator's output and appends the link sections to the end of the cover. With errors, it discards the output and draws the failure page as `index.md`. The behavior kept on purpose is in the external design's [Reports](../10-external/60-reports.md#the-cover-and-the-diagnostic-pages).

It is separated from the Generator so that the Generator does not carry the replacement on error, and so that the downstream site / publish need not distinguish the normal case from the failure case.

## Site Builder

`site`

Renders the generated Markdown into HTML.
