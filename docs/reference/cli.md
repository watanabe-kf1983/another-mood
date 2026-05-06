# CLI Reference

`mood` is the command-line entry point for Another Mood. It provides three subcommands: project initialization (`init`), one-shot build (`build`), and file watching with live preview (`watch`).

All subcommands take the target directory as the first positional argument `<project_dir>`. Typically you run them from inside the project directory and pass `.`:

```bash
mood init .
mood build .
mood watch .
```

## Commands

| Command | Purpose |
|---|---|
| [`mood init <project_dir> [--template <name>]`](#init) | Scaffold a project skeleton from a built-in template. |
| [`mood build <project_dir>`](#build) | Run all stages once and generate Markdown and HTML. |
| [`mood watch <project_dir> [--port <port>]`](#watch) | Watch for file changes, rebuild incrementally, and serve a preview. |

## Shared argument: `<project_dir>`

`<project_dir>` is given as a path relative to the current directory. Input paths are resolved against this directory, and output is written to `.another-mood/<project_dir>/` directly under the current directory.

### Input path resolution

Input paths (the schema file and the contents / queries / templates directories) are resolved relative to `<project_dir>`. Defaults:

| Kind | Default | Env var |
|---|---|---|
| Schema | `<project_dir>/definition/schema.yaml` | `RB_SCHEMA_FILE` |
| Content | `<project_dir>/contents` | `RB_CONTENTS_DIR` |
| Queries | `<project_dir>/definition/queries` | `RB_QUERIES_DIR` |
| Templates | `<project_dir>/definition/templates` | `RB_TEMPLATES_DIR` |

If any of these paths is missing when `build` or `watch` starts, the command fails and exits with code 1.

### Output path resolution

Output directories are placed under `.another-mood/<project_dir>/`, relative to the current directory:

| Kind | Default | Env var |
|---|---|---|
| Intermediate output (per stage) | `.another-mood/<project_dir>/tmp` | `RB_TMP_DIR` |
| Markdown output | `.another-mood/<project_dir>/output` | `RB_OUT_DIR` |
| HTML output | `.another-mood/<project_dir>/render` | `RB_RENDER_DIR` |

Subdirectories matching the input path are created automatically, so that running different `<project_dir>` values in parallel processes does not cause output collisions.

## init

Scaffold a project skeleton from a built-in template.

```bash
mood init <project_dir> [--template <name>]
```

Copies a built-in template into `<project_dir>`. If `<project_dir>` does not exist, it is created along with any missing parent directories.

### `--template`

Selects which built-in template to copy. Defaults to `starter`.

| Name | Description |
|---|---|
| `starter` | Minimal sample set of schema, contents, queries, and templates. |
| `ecommerce` | Worked example modelling an e-commerce catalog. |

Additional templates may be available — they correspond to the subdirectories of `showcase/` in the source tree. Passing an unknown name prints the list of available templates on stderr and exits with code 1.

Newly created files are listed with the `created:` prefix on stderr; files that already exist (and are therefore skipped) are listed with `warning:`:

```
Initializing project in my-project/ (template: starter)
  created: my-project/definition/schema.yaml
  created: my-project/contents/members.yaml
  ...
```

```
warning: skipped (already exists): my-project/definition/schema.yaml
```

The exit code is 0 if all files are newly created, or 1 if any file is skipped. Re-running `init` on an existing project never causes destructive changes.

## build

Run all stages once to generate Markdown and HTML.

```bash
mood build <project_dir>
```

Steps:

1. Loads `<project_dir>/definition/schema.yaml` and normalizes `<project_dir>/contents`.
2. Evaluates the queries under `<project_dir>/definition/queries` to build views.
3. Renders Markdown to `output/` using the templates in `<project_dir>/definition/templates`.
4. Renders the Markdown in `output/` into HTML in `render/`.

Exits with code 0 if all stages succeed, or 1 if any stage fails.

## watch

Watch files for changes, rebuild automatically, and serve a live preview.

```bash
mood watch <project_dir> [--port <port>]
```

When a change is detected on an input path (the schema file or the contents / queries / templates directories), only the affected stages re-run. The preview server detects file updates and auto-reloads connected browsers. Stop with `Ctrl+C`.

```
$ mood watch .
Press Ctrl+C to stop.
```

### `--port`

Specifies the port the preview server listens on. Defaults to `5077` (also overridable via the environment variable `RB_PORT`).

```bash
mood watch . --port 8080
```

To watch multiple `<project_dir>` values at the same time, start one process per project. Output directories are separated per `<project_dir>` and do not collide, but ports do — any process after the first needs `--port` to pick a different port.

## Configuration overrides

Every configuration key has a default; each can be overridden individually via an environment variable.

### Environment variables (`RB_*`)

Each configuration key can be overridden by an environment variable: prefix the key name with `RB_` and uppercase it as snake case. Values from environment variables are used as-is as paths; the default logic that derives paths from `<project_dir>` does not apply.

```bash
RB_CONTENTS_DIR=/abs/path/to/contents mood build .
RB_PORT=8080 mood watch .
```

### Keys and defaults

| Key | Default | Env var | CLI |
|---|---|---|---|
| `project_dir` | (required, given as argument) | — | first positional argument |
| `schema_file` | `<project_dir>/definition/schema.yaml` | `RB_SCHEMA_FILE` | — |
| `contents_dir` | `<project_dir>/contents` | `RB_CONTENTS_DIR` | — |
| `queries_dir` | `<project_dir>/definition/queries` | `RB_QUERIES_DIR` | — |
| `templates_dir` | `<project_dir>/definition/templates` | `RB_TEMPLATES_DIR` | — |
| `tmp_dir` | `.another-mood/<project_dir>/tmp` | `RB_TMP_DIR` | — |
| `out_dir` | `.another-mood/<project_dir>/output` | `RB_OUT_DIR` | — |
| `render_dir` | `.another-mood/<project_dir>/render` | `RB_RENDER_DIR` | — |
| `port` | `5077` | `RB_PORT` | `--port` (only on `watch`) |
