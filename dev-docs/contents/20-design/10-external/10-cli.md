# CLI

Behavior kept on purpose, outside the contract of `docs/reference/cli.md`. What the manifest's fields mean is in [Manifest](20-manifest.md).

Terms used in this chapter:

- **operator / user** — [Role terms](../index.md#role-terms)
- **agent** — an AI coding agent that runs `mood` from a shell. A kind of user, with no special treatment
- **`<project_dir>`** — the directory holding the sources. It is a project by virtue of containing `sbdb.yaml` ([Manifest](20-manifest.md))
- **CWD** — the directory `mood` was run in. Often the root of the user's repository
- **`out_dir` / `site_dir` / `tmp_dir`** — the settings that relocate the Markdown output, the HTML output, and the working directory (Keys and defaults in `docs/reference/cli.md`)
- **scaffold / blueprint** — `mood init` and `mood blueprint apply` creating a new project by copying a bundled sample project (a blueprint)
- **tap** — the single JSON document that `mood tap` emits, with the data and the views merged

## Entry points

### There is no validate-only command; build covers it

There is no command like `mood validate` that validates without building. The tool never modifies the sources and returns the same output for the same input, so repeating build does no harm. Whether there were errors is available from the exit code, and the output can be discarded if it is not wanted.

### No agent-only entry point, and no agent-only text

There is no entry point reserved for agents, such as an MCP server. An agent runs the same `mood` from a shell as a human does, and reads the same `docs/` through `mood docs`, the command that shows the bundled documentation. The way to use the tool is identical for humans and agents, and no separate edition is needed.

A dedicated entry point breeds text that exists only on that route (such as instructions injected into the agent on connection), and the documentation then has two sources of truth. This happened when we had an MCP server, and the entry point was dropped altogether.

An agent arriving at a project is pointed the right way by the `README.md` that scaffold generates at the project root. It says only what is managing the directory, how to get the tool, and where help and the documentation start; it does not describe structure or procedures. That is the job of `mood --help` and `docs/`.

### watch runs in the foreground and has no detach option

There is no way to start and stop in the background, such as `mood watch --detach`. A human starts `mood watch <dir>` in the foreground in a terminal they can see, and an agent tells the user to "run it in another terminal".

All that detaching saves is starting watch once at the beginning of the work. watch is something a human keeps running for the whole stretch of work, not something started and stopped at every turn of an agent's conversation or task.

As a hidden daemon, it loses the route for observing build errors on the spot. It is not worth the maintenance debt of subprocess, signal, and platform branches.

## Locations

### The layout of the sources cannot be moved by settings

Paths such as `definition/schema.yaml` are derived from `<project_dir>`, and there is no way to override them individually. The layout is one of the format's contract surfaces ([Manifest](20-manifest.md#sbdb_version-is-one-integer-for-the-whole-format-and-does-not-rise-when-the-tools-contract-breaks)); claiming a generation with `sbdb_version` while moving the files around would contradict the declaration.

### Output goes to `.another-mood/` directly under the CWD, not into the project

`<project_dir>` is the user's content area, and from the tool's point of view a thing to read. Nothing is written into it; by default the output goes to `.another-mood/` directly under the CWD:

- The `.` prefix is the convention for a framework's working area, like `.next/` and `.pytest_cache/`
- The gitignore is one line at the root, `/.another-mood/`
- If the input is another repository (a git submodule, say), it is not polluted
- It stays out of sight of whoever edits `contents/`

### `<project_dir>` must be under the CWD; the output destinations are not restricted

The output is divided into `.another-mood/<project_dir as seen from the CWD>/`, so processing different `<project_dir>`s at the same time does not collide. This relative path is defined only when `<project_dir>` is under the CWD, so pointing outside (escaping with `../`, or an absolute path outside) is refused.

Dividing by basename alone is not adopted: `/a/proj` and `/b/proj` would land in the same place.

`out_dir` / `site_dir` / `tmp_dir`, which replace this default, are a separate concern ("where to write"), and writing outside the CWD has legitimate uses, so they are not restricted. A replaced destination is used as given, without subdividing.

## tap

### tap does not mirror the shape of the sources; it emits the tree after normalization and merging

It might seem enough for the user to read `contents/` directly, but the sources are shaped for the author to write, not for querying. The output of tap differs from the sources in the following ways, and this difference is kept:

- The shape is uniform. Sources may be written in the map pattern (`{id: {...}}`), but the output is the normalized array, so `jq 'map(select(...))'` works as is
- It is merged. Sources are split across files and merged into one tree at build time ([Schema](30-schema.md#one-collection-can-be-written-across-several-files)). Reading them directly, the user would reimplement this merge
- It is one format. Sources mix YAML and Markdown; the output is one tree
- The views are in it. The results of join and grouped are not in the sources, and tap is the only place to get them

### It only produces the document; there is no query interface

tap produces one JSON document and stops. It has neither a query argument like `--jq` nor a partial selection of top-level views; narrowing down is left to the user's tools (jq, scripts).

What a jq argument would rescue is only a client with no shell and no file sharing (an agent that can query only through MCP). Today's readers are external programs on the CLI route and agents with a shell; the shell-less client is still hypothetical.

We do not pay up front for a hypothetical reader: the dependency on a jq engine (the `jq` on PyPI is a C extension) and the design of its error surface and result format. When a client without a shell appears, a jq argument can be added as a pure addition.

Partial selection is omitted for the same reason. Even the whole of dev-docs is a document of about 600 KB, and the cost of piping it into jq is not worth counting. A selector would reimplement what jq already does.

As a side effect, because mood has no query interface at all, the only notion of a query mood has is the DSL of view definitions ([View](40-view.md)).

### The output is JSON only

Since querying is delegated to jq, the output must be in a form jq can consume as is, and jq does not read YAML. JSON is also what an external program can read with its standard library alone. YAML output can be added as a pure addition when a real need appears.

### The document holds no value that changes from run to run

Build info and timestamps are not put into the tap document. Users often diff tap's output between runs, and a value that changes every time buries the difference they want to see. Values derived from the sources (`__definition` and the like) may be included.
