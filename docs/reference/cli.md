# CLI Reference

`mood` is the command-line entry point for Another Mood. The day-to-day workflow uses `init` (first time), `build` (one-shot rebuild), and `watch` (live preview). `mood blueprint` is a separate command group for managing the built-in sample projects that `init` is built on top of.

`init`, `build`, and `watch` take the target directory as the first positional argument `<project_dir>`. Typically you run them from inside the project directory and pass `.`:

```bash
mood init .
mood build .
mood watch .
```

## Commands

| Command | Purpose |
|---|---|
| [`mood init <project_dir>`](#init) | Shortcut for `mood blueprint apply starter <project_dir>`. |
| [`mood build <project_dir>`](#build) | Run all stages once and generate Markdown and HTML. |
| [`mood watch <project_dir> [--out-dir <dir>] [--host <addr>] [--port <port>]`](#watch) | Watch for file changes, rebuild incrementally, and serve a preview. |
| [`mood blueprint list`](#blueprint-list) | List the available blueprints. |
| [`mood blueprint apply <name> <project_dir>`](#blueprint-apply) | Apply a blueprint into a project directory. |
| [`mood docs list`](#docs-list) | List bundled documentation entries with their `docs://` URIs. |
| [`mood docs read <uri>`](#docs-read) | Print the contents of a bundled doc by its `docs://` URI. |

## Shared argument: `<project_dir>`

`<project_dir>` is given as a path relative to the current directory. Input paths are resolved against this directory, and output is written to `.another-mood/<project_dir>/` directly under the current directory.

`build` and `watch` cannot target a `<project_dir>` outside the current directory.

### Source layout

Source paths are fixed — they are part of the project structure, not configuration, and cannot be overridden:

| Kind | Path |
|---|---|
| Schema | `<project_dir>/definition/schema.yaml` |
| Reports | `<project_dir>/definition/reports.yaml` |
| Content | `<project_dir>/contents` |
| Queries | `<project_dir>/definition/queries` |
| Templates | `<project_dir>/definition/templates` |

If any of these paths is missing when `build` or `watch` starts, the command fails and exits with code 1.

The project [manifest](manifest.md) (`<project_dir>/sbdb.yaml`) also lives at a fixed path.

### Output path resolution

`build` places its Markdown and HTML output under `.another-mood/<project_dir>/`, relative to the current directory:

| Kind | Default | Env var |
|---|---|---|
| Markdown output | `.another-mood/<project_dir>/output` | `RB_OUT_DIR` |
| HTML output | `.another-mood/<project_dir>/render` | `RB_RENDER_DIR` |

Subdirectories matching the input path are created automatically, so that running different `<project_dir>` values in parallel processes does not cause output collisions.

`watch` publishes nothing by default: it serves the preview live and writes no files into the project, so `mood build` stays the only writer of `output/`. Pass [`--out-dir <dir>`](#watch) to also publish the Markdown tree; `watch` never publishes HTML.

## init

Shortcut for the most common case: applying the `starter` blueprint.

```bash
mood init <project_dir>
```

Equivalent to `mood blueprint apply starter <project_dir>`. Use `mood blueprint apply` directly to pick a different blueprint.

## build

Run all stages once to generate Markdown and HTML.

```bash
mood build <project_dir> [--strict]
```

Steps:

1. Loads `<project_dir>/definition/schema.yaml` and normalizes `<project_dir>/contents`.
2. Evaluates the queries under `<project_dir>/definition/queries` to build views.
3. Renders Markdown to `output/` using the templates in `<project_dir>/definition/templates`.
4. Renders the Markdown in `output/` into HTML in `render/`.

Exits with code 0 if all stages succeed, or 1 if any stage fails.

### `--strict`

Fail the build (exit code 1) when any warning is reported. Without `--strict`, warnings (e.g. a dangling [`x-ref`](schema.md#entity-references-x-ref) value) are listed on a dedicated page at `output/__warnings/`, linked from `output/index.md`, but do not affect the exit code. Useful in CI to gate merges on a clean build.

## watch

Watch files for changes, rebuild automatically, and serve a live preview.

```bash
mood watch <project_dir> [--out-dir <dir>] [--host <addr>] [--port <port>]
```

When a change is detected on an input path (the schema file or the contents / queries / templates directories), only the affected stages re-run. The preview server detects file updates and auto-reloads connected browsers. Stop with `Ctrl+C`.

By default `watch` writes nothing into the project — the preview is served live from a temporary working directory, and the diagnostic views are browsable at `/__db/`. Use `--out-dir` to also publish the Markdown tree to disk.

```
$ mood watch .
Press Ctrl+C to stop.
```

### `--out-dir`

Publish the Markdown output tree to `<dir>` on each rebuild. Without it, `watch` publishes nothing; naming a destination is the opt-in. Only Markdown is published — `watch` has no `--render-dir`, since the live server is the HTML consumer; run `mood build` for static HTML.

```bash
mood watch . --out-dir ./public
```

Pointing `--out-dir` at the project's own `.another-mood/<project_dir>/output` restores the pre-isolation behavior, where a concurrent `mood build` or a reader of `output/` can race the rebuild's republish — prefer a separate directory.

### `--host`

Specifies the bind address of the preview server. Defaults to `127.0.0.1` (loopback only; also overridable via the environment variable `RB_HOST`). Pass `0.0.0.0` to expose the server on the LAN, e.g. so attendees of a design meeting can browse the docs as the author edits them:

```bash
mood watch . --host 0.0.0.0
```

The preview server has no authentication, so use this only on trusted networks. When `--host 0.0.0.0` (or `::`) is given, the URL printed at startup substitutes a routable LAN address for the wildcard so it can be copy-pasted directly.

### `--port`

Specifies the port the preview server listens on. Defaults to `5077` (also overridable via the environment variable `RB_PORT`).

```bash
mood watch . --port 8080
```

To watch multiple `<project_dir>` values at the same time, start one process per project. By default nothing is published, so their outputs cannot collide; ports do — any process after the first needs `--port` to pick a different port. (If you pass `--out-dir`, give each project a distinct directory.)

## blueprint

A *blueprint* is a working sample project (schema, contents, queries, templates) bundled with Another Mood. The `blueprint` command group lists them and applies them to a target directory.

### blueprint list

```bash
mood blueprint list [--names-only]
```

Prints the available blueprints to stdout in a man-page style: each blueprint takes two lines — the name on the first, the description (indented) on the second.

Pass `--names-only` to print just the names, one per line, suitable for scripting (e.g. iterating over blueprints in a shell loop or Makefile).

### blueprint apply

```bash
mood blueprint apply <name> <project_dir>
```

Applies the named blueprint by copying its sources into `<project_dir>`. If `<project_dir>` does not exist, it is created along with any missing parent directories. Passing an unknown blueprint name fails with the available list.

A fresh [manifest](manifest.md) (`sbdb.yaml`) is also generated. Files unrelated to Another Mood (`.git`, `README.md`, …) are left alone, but a blueprint is never merged into an existing project: applying into one fails without writing anything.

## docs

Inspect the documentation that ships with Another Mood. The same catalog is exposed to AI agents as MCP Resources and Tools; these CLI commands give you the same view from the terminal.

### docs list

```bash
mood docs list
```

Prints each bundled doc's `docs://` URI and description on two lines (URI on the first, indented description on the second), in the order defined by the catalog manifest.

### docs read

```bash
mood docs read <uri>
```

Prints the contents of the bundled doc identified by `<uri>` to stdout. `<uri>` must be one of the values printed by `mood docs list` (e.g. `docs://reference/cli.md`). Passing an unknown URI prints an error to stderr and exits with code 1.

## Configuration overrides

Every configuration key has a default; each can be overridden individually via an environment variable.

### Environment variables (`RB_*`)

Each configuration key can be overridden by an environment variable: prefix the key name with `RB_` and uppercase it as snake case. Values from environment variables are used as-is as paths; the default logic that derives paths from `<project_dir>` does not apply.

```bash
RB_OUT_DIR=/abs/path/to/output mood build .
RB_PORT=8080 mood watch .
```

### Keys and defaults

| Key | Default | Env var | CLI |
|---|---|---|---|
| `project_dir` | (required, given as argument) | — | first positional argument |
| `tmp_dir` | (per-run session dir under the system temp dir) | `RB_TMP_DIR` | — |
| `out_dir` | `build`: `.another-mood/<project_dir>/output`; `watch`: unset (publishes nothing) | `RB_OUT_DIR` | `--out-dir` |
| `render_dir` | `build`: `.another-mood/<project_dir>/render`; `watch`: not published | `RB_RENDER_DIR` | `--render-dir` (only on `build`) |
| `host` | `127.0.0.1` | `RB_HOST` | `--host` (only on `watch`) |
| `port` | `5077` | `RB_PORT` | `--port` (only on `watch`) |
