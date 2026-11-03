# Manifest

Behavior kept on purpose, outside the contract of `docs/reference/manifest.md`. How the manifest is separated from config and layout, and in what order they are read, is in [Architecture of the internal structure](../20-internal/10-architecture.md#the-three-things-received-at-startup).

Terms used in this chapter:

- **format (sbdb)** — the format of the sources the user writes. sbdb is short for source-based database. It covers how the schema, views, prose, templates, and manifest are written, and where they are placed in the project. It is a tool-independent spec, and Another Mood is one tool that processes it
- **generation** — a version of the format. The integer written in `sbdb_version`, corresponding to Rust's edition or Kubernetes' apiVersion
- **minimum version** — the lowest version of the tool needed to process this project. Written in `tools.another-mood.minimum_version`
- **strict parsing** — when the input holds something unknown to the vocabulary the tool defines, raising an error rather than silently skipping it
- **contract surface** — one of the areas that make up the format: schema, views, prose, templates, layout, manifest ([what `sbdb_version` speaks for](#sbdb_version-is-one-integer-for-the-whole-format-and-does-not-rise-when-the-tools-contract-breaks))
- **silent corruption** — broken output produced without an error
- **`definition/` / `contents/`** — the project's two directories. The former holds the schema, views, and templates; the latter holds the data (Source layout in `docs/reference/cli.md`)
- **author / operator / user** — [Role terms](../index.md#role-terms)
- **config** — what the operator hands over at startup through CLI arguments and environment variables: how to run and where to write ([Architecture](../20-internal/10-architecture.md#the-three-things-received-at-startup))
- **scaffold / blueprint** — terms of [CLI](10-cli.md)

## Version checks

### Three things make an old-new mismatch fail loudly: the generation declaration, the minimum version declaration, and strict parsing

Between sources written by humans and a tool that evolves independently of them, each side has an old and a new, so there are four combinations. The dangerous ones are the two mismatches, and either can be silent corruption:

- A new tool reads old sources — the tool changed the meaning of existing syntax but interprets the old sources as they are
- An old tool reads new sources — the old tool skips syntax it does not know

The second splits further in two. If the new sources use newly added syntax, that is unknown input to the old tool. If they are sources written after the meaning of existing syntax changed, the old tool reads syntax it knows with the old meaning.

The purpose of the version checks is to detect these and fail loudly. Old sources are not migrated automatically.

The three instruments are not redundant insurance; they divide the work:

- **The generation** (`sbdb_version`) rises on a breaking change that alters the meaning of existing syntax, and not when syntax is added (the only exception is the prose surface, below). The tool holds the set of generations it supports, and refuses anything outside it. In either direction, it covers the combinations that read changed syntax with a different meaning
- **Strict parsing** turns added syntax into an error when an old tool reads it, as unknown input. It is the last line of defense, working even when the minimum version is not declared or has gone stale
- **The minimum version** declares that a tool of at least this version is needed, and produces the exact error "upgrade the tool". It is an optional field, and the tool does not demand that the declaration be updated when the sources later come to depend on a newer feature

Because strict parsing catches added syntax (except in the body of prose; see [the table of unknown input](#unknown-input-is-an-error-not-silently-skipped)), the generation only has to rise when meanings change, and revisions stay infrequent.

Since updating the minimum version is not demanded, strict parsing is the only thing that stops the combination "sources using an added feature, read by an old tool under an old declaration".

### `sbdb_version` is one integer for the whole format, and does not rise when the tool's contract breaks

The unit of declaration and checking is the single `sbdb_version`; there is no version per contract surface such as schema, views, or templates. If the user writes one field, there is no field to forget.

It is an integer because, when outside the supported set, comparing magnitudes tells the direction: whether to upgrade the tool or migrate the project. The three digits of semver are the vocabulary of an ecosystem with a dependency resolver, where the tool decides what is compatible.

The contract surfaces that make up the format are as follows. Whether a change is breaking is judged by whether it edited any of them incompatibly:

| Contract surface | What it binds |
|---|---|
| schema | What can be written in `definition/schema.yaml` (bound by the tool's `resources/schemas/schema-schema.yaml`) |
| view | What can be written in a view definition (likewise `view-schema.yaml`) |
| parser/prose | The interpretation of Markdown files: how headings and links in the body are read, and the schemas of the built-in prose / blob |
| template | The vocabulary callable from templates (filters, tags, functions) |
| layout | The placement within the project (`definition/` / `contents/`) |
| manifest | What can be written in `sbdb.yaml`, excluding the two frozen fields ([The fields that declare versions are frozen in place and shape](#the-fields-that-declare-versions-are-frozen-in-place-and-shape)) and the contents of each tool's `tools.<name>` |

The template vocabulary counts as a surface because the user's templates depend on it. If another processor appears, it will come to implement this vocabulary too.

contents has no contract surface of its own. What binds the data written in contents is the user's `schema.yaml`, and a tool change that alters the meaning of contents always shows up as a change to the schema surface or the parser/prose surface.

The number speaks only for format compatibility between sources and tool. A change that breaks the tool's own user-facing contract, such as the CLI, does not raise it. The format is a tool-independent spec; a version rising for one tool's convenience would break the separation of spec from tool.

Breaking the tool's contract, and the procedure when a generation drops out of the supported set, belong to the [release flow](../../30-dev/40-release.md). There is no history of which surface moved incompatibly in which generation. The PR that introduces a breaking change writes the migration steps in docs itself, so no reader has to assemble migration steps from history.

### `sbdb_version` is required, with no default when omitted

Without the field there is nothing to check. Silently interpreting new-generation sources whose declaration was forgotten as the old generation is exactly the silent corruption we want to prevent. Cargo treats an omitted `edition` as the oldest edition, but that is a compromise forced by assets it cannot break, and a tool that has not reached 1.0 does not need it.

A directory without `sbdb.yaml` is an error for the same reason, indistinguishable from a missing field. Without a manifest the generation cannot be read, and reading with a default generation would be the same silent corruption. scaffold writes it, so there is no burden on someone starting out.

### The fields that declare versions are frozen in place and shape

The name and format of the `sbdb_version` field, and the shape of `tools.<name>`, stay in the same place in the same form across generations. For an old tool to correctly refuse a file of a future generation with "unsupported", every generation of the tool must be able to read at least these two fields.

A file of a future generation is refused as an "unsupported generation", not as "unknown keys". For that, loading first reads only the frozen fields and passes the version check, and only then validates the whole file strictly.

Only these two fields are frozen; other fields can be added without changing the meaning of existing ones, so the generation does not move. Metadata such as author or license can be added when needed without moving the generation, so it is not included now.

### The minimum version is a per-tool field, placed under `tools:`

The format is tool-neutral, so tool names are not mixed into its vocabulary. A tool's version floor is a per-tool concern, and following pyproject.toml's split between `[project]` and `[tool.<name>]`, it lives under the `tools:` namespace.

If another processor appears, each has its own line. The lines of other tools are not inspected; they ignore each other. Under `tools.another-mood` is Another Mood's vocabulary, so unknown keys there are errors.

### The minimum version is a verified floor, and only a bare version is accepted

What is declared is the version "confirmed to work"; the true minimum may be lower, and finding it is not required. As it is only a floor, scaffold can mechanically write the running version at generation time.

Ranges and operators are not accepted. Every system where a build tool reads a manifest from the sources (Go, Rust's `rust-version`, CMake) does the same; the vocabulary of ranges belongs to systems with a dependency resolver. An upper bound cannot be known at the time of writing. If one is needed, a separate field can be added without breaking compatibility.

### Unknown input is an error, not silently skipped

If there is unknown input in the vocabulary the tool defines (schema keys, view definition operators, template tags / filters / functions, manifest keys), it is an error. This property is kept when features are added. It is the last line of defense for a user who has not declared, or has not updated, the version ([division of work](#three-things-make-an-old-new-mismatch-fail-loudly-the-generation-declaration-the-minimum-version-declaration-and-strict-parsing)).

Who handles it, per contract surface:

| Contract surface | Treatment of unknown input |
|---|---|
| schema / view | Rejected by the side that validates schema and view definitions (the tool's meta-schemas). The keys of contents are decided by the user's `schema.yaml`, and whether unknown keys are rejected depends on how it is written, so they are not the tool's vocabulary |
| parser/prose | Not covered. The body is free Markdown, and unknown input cannot be told from body text. Added embedded syntax passes as body text too, so on this surface alone both additions and changes of meaning are left to the generation |
| template | Calling an unknown tag, filter, or function is an error. Merely referring to an undefined name, however, yields empty. That is for ease of writing names that come from the user's data (kinds of data and attributes), not a hole in compatibility. The names the tool adds are functions and filters to be called, so calling one that an older tool does not know raises an unknown-name error |
| layout | Directly under `definition/` only known entries may exist. The project root shares space with `.git` and `README.md`, so it is not checked. Inside `definition/views/` is covered by view validation, and `definition/templates/` is an open namespace the user names, so the depth of the check stops at the top level |
| manifest | Rejected at load time |

## Location and role

### The manifest is outside contents, and whoever writes contents need not know the version

Declaring the version is the concern of whoever writes definition, and contents has no contract surface ([what `sbdb_version` speaks for](#sbdb_version-is-one-integer-for-the-whole-format-and-does-not-rise-when-the-tools-contract-breaks)), so it is placed where whoever writes contents does not see it.

Yet not inside `definition/` either. The manifest speaks, like `title`, about the project as a whole including contents, so it sits at the project root, next to `definition/` and `contents/`. The same placement as Cargo.toml or package.json.

### The manifest declares "what this is" and holds no "how to build"

The manifest is the identity of the project (the display name in the `title` field) and its compatibility declaration, distributed together with the project. How to run and where to write (the output destination, the port, the values passed to templates) are decided by the operator on the spot, and handed over at startup through CLI arguments and environment variables ([CLI](10-cli.md)).

Someone else building the same project somewhere else need not rewrite the manifest. Conversely, there is no way for config to move the format's generation or layout ([CLI › The layout of the sources cannot be moved by settings](10-cli.md#the-layout-of-the-sources-cannot-be-moved-by-settings)).
