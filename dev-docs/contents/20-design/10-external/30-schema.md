# Schema

Behavior kept on purpose, outside the contract of `docs/reference/schema.md`. The stage names in this chapter (`inspect_schema`, `normalize_contents`, `generate`) are those of the [stage table of the internal structure](../20-internal/20-pipeline.md#stages).

Terms used in this chapter:

- **x-ref** — the declaration that a property's value points at a record of another entity (Entity references in `docs/reference/schema.md`)
- **singleton** — a single object that is not a collection (Single-record pattern, same document)
- **database pages** — the pages under `__db/` that the tool draws automatically from the schema and view definitions

## Schema language

### What is removed from JSON Schema is the syntax that stops it from reading as a data model

`definition/schema.yaml` is a subset of JSON Schema draft 2020-12. The list of what is accepted is in `docs/reference/schema.md`.

There is one criterion for removal: keep the schema readable as the declaration of a [data model](../../10-concept/10-product.md#data-model-a-json-tree-with-discipline), not as a bundle of validation rules. Every construct maps one-to-one onto an entity (a set of records of the same shape) or an attribute (a value with one type). Queries and templates can be written assuming this shape.

When tempted to add expressive power from JSON Schema, judge by whether this one-to-one mapping survives. The removed constructs, and what to write instead:

| Removed construct | Instead |
|---|---|
| Composition and conditionals (`allOf` / `anyOf` / `oneOf` / `not` / `if`), the array form of `type`, the `null` type | Split attributes by type (`contact` → `email` and `address`). Express the absence of a value by omitting the key |
| `$ref` / `$defs` | If records of the same shape appear in several places, gather them into one entity and point at it with an x-ref. If only the type is to be shared, write it twice. Reading top to bottom without jumping to a definition matters more than avoiding duplication |
| Bare `type: object`, `type: array` without `items` | Data of indeterminate shape is held as a string attribute |
| `$comment` | YAML comments |

The schema is one file with one root, and the root's `properties` lists the entry to each entity. It is the opposite shape to OpenAPI's `components.schemas`, which lists a named type for every fragment flowing through an API: it declares the one body of data accumulated in `contents/` as one object.

### Literals written in the schema also follow the declared type

The values of `default` / `examples` / `enum` / `const` must match the `type` of the same declaration, or it is an error. `default: 5` under `type: string` does not pass. JSON Schema itself does not check this.

Two reasons. A mismatch is always a writing mistake, and if it passed silently, the `default` shown on the database pages would contradict the type.

Also, a value written in the schema is data too. It is copied into the [data catalog](../20-internal/30-communication/20-data-catalog.md), persisted, and read back by `generate`. So the constraints of the [JSON data model](../20-internal/30-communication/10-json-data-model.md) apply.

The date type YAML makes from `2024-01-01` cannot be represented in JSON and matches no declarable `type`. Requiring literals to match their type closes the door through which a date type could enter the pipeline.

Not written in `docs/`. The user meets this when the build stops, and the error points at the line and column.

## x-ref

What is kept behind Entity references in `docs/reference/schema.md`.

### Only a `type: string` property can carry one

References are matched by comparing strings. The target `id` is always a string ([An id made from a map pattern key is always a string](#an-id-made-from-a-map-pattern-key-is-always-a-string)). Allowing an x-ref on an integer property would make `2024` and `"2024"` fail to match, and the type difference would surface as a dangling-reference warning whose cause is hard to see.

### The target must be an entity reachable from the root without crossing another collection

A nested collection (`screens.buttons`) is part of the parent record, read and written as one with it. Wanting to reference it from elsewhere is the signal to extract it as an independent entity. Fix it on the data model side, not with a syntax extension that lets a nested path be written as a target.

There is a mechanical reason too. A record's id is [unique only among siblings](#unique-only-among-siblings), so the set of every screen's buttons may hold duplicate ids. Only a collection within which ids are unique is meaningful as a target. A singleton is not a collection, so `site_config.items` does not cross one.

The catalog's self-description `__definition.*` is not a target either. A reference to schema metadata is not a relation in the data.

### Its meaning is an enum check against the set of the target's values

It checks whether the value is in the set of the target attribute's values: a dynamic version of enum validation. The surrounding treatment follows from this view, with no rules of its own:

- No value, no check (a non-required property omitted). There is no enum to apply
- The empty string is an ordinary value. If the target has no `""`, the reference dangles
- A self-reference (`genres.parent_id` → `genres`) needs no special rule. The set just includes itself
- Cycle detection and multiplicity (1:N, N:M) are outside the responsibility of x-ref

The premise is that the target set is uniquely determined. A property whose target depends on the value (multiple targets) is not supported; hold it as a free string without an x-ref.

### A dangling reference does not stop the build

An inconsistency on the schema side (a target naming a nonexistent entity or attribute) stops the build before the data is read. A dangling reference on the data side is only a warning, and the pages are drawn.

Data in the middle of being written normally has targets not yet in place, and if the build could not be seen until they were, the write-and-check loop would stall. x-ref is opt-in per property, so warnings appear only where it was added. To reject them in CI, use `--strict` (`docs/reference/cli.md`).

## How `contents/` is read

### JSON is the inlet for what another program emitted once

Behind the advice to write YAML by hand and reserve JSON for the output of other programs (Which files are read in `docs/reference/cli.md`). JSON is the entry for data that another program emits once and is done with, such as an LLM's structured output, a build tool, or a cron job.

A person writing by hand, or an agent writing interactively, can run the build and fix errors in a loop. For such writers, YAML with its readable Git diffs suits. A program that emits once has no such loop, so its data must be accepted in the format it can produce. An LLM's structured output being built for JSON is the typical case.

### Duplicate keys are errors

If the same key appears twice in one file, it is an error, and the later value is not taken. The same in YAML and JSON, and not only in contents but in schema and view files too. The reason lies on the data side, so it is placed here.

The JSON specification (RFC 8259) leaves duplicate keys to the implementation, and many implementations silently take the later value. Stopping is safer than a value silently vanishing.

Not written in `docs/`. The user meets this when the build stops, and the error points at the line and column like any other syntax error.

### One collection can be written across several files

Each file in `contents/` is part of the tree, and all files are merged into one tree before being passed downstream. The merge is deep: objects recursively, arrays by concatenation. This lets the records of one collection be written in files per topic, and how the files are divided does not affect the shape of the data.

Accordingly, duplicate record ids and x-refs (references to other records; Entity references in `docs/reference/schema.md`) are checked on the merged tree, not per file.

## Record ids

### Unique only among siblings

Records in the same array sharing an id is an error. With different parents, the same id means different records and does not collide. A record's address (its anchor path; Anchor paths in `docs/reference/template.md`) is made by appending the id to the parent's address, so uniqueness among siblings makes the address unique too.

### An id made from a map pattern key is always a string

When a map pattern is turned into an array, the key becomes the `id` as is. A YAML key can be a number, boolean, or date (`2024:` is read as an integer), but a non-string key is converted to a string for the id. Reasons:

- The intermediate files passed between stages are JSON ([JSON data model](../20-internal/30-communication/10-json-data-model.md#serialization-formats)), and YAML keys can have types such as dates that JSON cannot represent
- The [data catalog](../20-internal/30-communication/20-data-catalog.md) declares id as a string. The actual data's type follows the declaration
- An x-ref can only be placed on a string attribute (`docs/reference/schemas/schema-schema.yaml`). If ids are strings, matching references is a comparison of strings
- Whoever assembles anchor paths can assume ids are always strings

`docs/reference/` does not describe this conversion. A user writing an integer key such as `2024:` means "a label that says 2024", and the result matches that expectation, so no explanation is needed.

## prose

### The reading order is encoded in the id, and id stability is given up

A prose id is the relative path from `contents/` (without extension) itself, and the reading order is the string order of ids. There is no separate channel for order (front matter, a table-of-contents file), so order is expressed in file names.

Zero-padded, gapped number prefixes (`10-architecture.md`; a folder's `index` gets none) are one such practice, and dev-docs uses it.

The following three cannot all hold at once:

- **The reading order is visible on the file system** — the order has to be in the file name, and if the id is the path itself, the order is in the id too
- **The id is stable under reordering** — links between documents use the id as the address, so unless it is stable, reordering breaks links. Incompatible with the first
- **The file system guarantees id uniqueness** — declaring the id separately reconciles the first two, but loses this, and a duplicate check has to be kept in-house

This decision gives up the second. A prose chapter structure settles early, and gapped numbers mean insertion needs no renumbering. Links broken by reordering are reported by `generate`'s link resolution.

### Order derivation is per record; sorting is the template's

`order_key` and `depth` can be derived from the id alone, so `normalize_contents` attaches them per record. Sorting needs the whole collection, so it is placed on the template side (`sort(attribute="order_key")`), and no pre-sorted prose is provided.

Binding a folder tree into one book with nested headings (the book edition in `dev-docs/definition/reports.yaml`) can be written with just these two and the `under_heading` filter (`docs/reference/template.md`).

### Heading ids are GitHub-compatible slugs

A heading's id is the GitHub-compatible slug derived from the heading text (`## API の設計` → `api-の設計`). A link to a heading then lands in the same place whether viewed in this tool's Hugo output, on GitHub, or in VS Code's preview. The source of truth for the rule is the docstring of `github_slug`.

Explicit notation such as `{#id}` is not adopted. Derived from the text, the id and the heading cannot drift apart. Id stability is secured not by "never changing" but by "the build reports a broken reference".

### Relative links become `node:`; a `#fragment` within the same page is not converted

Every relative link in the body that resolves within `contents/` is rewritten to `node:` notation (addressing the target by a record's address; Anchor paths in `docs/reference/template.md`).

When the split granularity changes per edition (`docs/reference/reports.md`), the target's page changes too, so a raw relative path left as is breaks in the output of another split. Converted to `node:` and left to `generate`'s resolution, links follow even when the output structure changes. A `#fragment` rides on the `node:` URI for the same reason.

A pure `#fragment`, on the other hand, is not converted. A prose file is always drawn whole onto one page, so a reference within the same document always lands within the same page and does not break.

The rewrite is lexical; whether the target exists is not checked here. Existence is left to `generate`'s link resolution, and a broken one is made conspicuous ([Template](50-template.md#an-unresolved-reference-is-made-conspicuous-as-text)).

Links are not checked as x-refs either. An x-ref is a data concern that guarantees a join target in queries; a link is a concern of the output world. So links to headings are not bound by x-refs, and headings are not raised into entities.

## blob

### The id includes the extension

A blob id is the relative path from `contents/`, extension included. Dropping it would make `fig.png` and `fig.jpg` collide. The extensionless prose id is an omission that works only because `.md` is the sole extension, and it is not applied to blob.

### The bytes are not carried on the record

A blob record holds only id and mime_type, not the bytes of the content. Carrying them as base64 would bloat the record and break memory and Git diffs. The location of the real file can be recovered from the id, so the side that carries the bytes to the output ([transport](../20-internal/30-communication/index.md#transport)) reads from there.
