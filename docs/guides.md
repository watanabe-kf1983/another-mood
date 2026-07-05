# Guides

## What is Another Mood?

Requirements specifications, product catalogs, maintenance manuals, training materials — in documents like these, you keep meeting the same characters — "users", "products", "procedures" — appearing in different shapes again and again. Each time you introduce a new one, you end up revising it in several places, missing one somewhere, and the documents drift out of sync before you notice.

**Another Mood** is a processor of source-based databases — a tool that keeps document sets like these in sync. Edit the data in one place, and every linked output regenerates in a consistent state — no chasing fixes through many files.

A **source-based database** is a database made of files that you create, update, and delete — these files are referred to as **sources** in the rest of this guide. Sources are written in formats like YAML and Markdown (the specific layout is covered in [Source structure](#source-structure)). Editing sources directly in an editor is the only way to interact with the database.

Another Mood reads the sources and produces query results, data tables, and template-based documents. You review these outputs and keep editing the sources accordingly.

### Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package and project manager.

## Quick Start

### Install

With uv installed:

```bash
uv tool install git+https://github.com/watanabe-kf1983/another-mood.git
```

This puts the `mood` command on your PATH (along with `mood-mcp` — see [Using with AI agents](mcp.md)).

### Scaffold a sample and build

```bash
mood init my-project
mood build my-project
```

`mood init` scaffolds a minimal source-based database sample (a member list) under `my-project/`. `mood build` converts it to Markdown and HTML.

What you write (under `my-project/`):

```
my-project/
├── definition/
│   ├── schema.yaml                       # data types
│   ├── reports.yaml                      # which records become their own page
│   ├── queries/
│   │   ├── by_role.yaml                  # group by role
│   │   └── active_members.yaml           # filter to active members
│   └── templates/
│       ├── index.md                      # home-page template
│       ├── member.md                     # member detail
│       └── by_role.md                    # listing by role
└── contents/
    └── members.yaml                      # data (3 members)
```

What the tool generates (under `.another-mood/my-project/`):

```
.another-mood/my-project/
├── output/                                   # Markdown
│   ├── default/                              # your templates' pages
│   │   ├── index.md                          # home page (from templates/index.md)
│   │   ├── members/{alice,bob,carol}.md
│   │   └── by_role/{engineer,designer}.md
│   ├── index.md                              # cover: your reports + link to __db/
│   └── __db/                                 # the database's self-description
│       ├── index.md                          # auto overview (entities + queries)
│       ├── __entity_defs/                    # described later
│       ├── __entity_data/                    # described later
│       └── __queries/                        # described later
└── render/                                   # HTML
```

Your templates render to `output/default/`. Inside it, since there are 3 members, one file is generated per member under `members/`, and with 2 roles, one file per role under `by_role/`. The root `index.md` template loops through the data and emits these subpages as it goes — this is the core mechanism of the tool. The [Templates](#templates) chapter covers it in detail.

Besides `default/`, `output/` also holds pages the tool generates on its own. The root `index.md` is a thin **cover** — it lists your reports (here just `default/`) and links to `__db/`, the database's self-description: an overview (`__db/index.md`, the entities and queries) plus the `__`-prefixed diagnostic directories. Independent of your templates, they let you check the current state of the schema, data, and queries while writing — see the [Workflow](#workflow) chapter for details.

### Try the live preview

```bash
mood watch my-project
```

`http://localhost:5077` displays the HTML in your browser. Edit any file and save: the project auto-rebuilds and the browser reloads. Try changing `alice`'s `role` in `contents/members.yaml` from `engineer` to `manager`. You'll see `output/default/by_role/manager.md` newly appear, and `alice` disappear from `output/default/by_role/engineer.md` (the same changes show in the browser pages). One line of data edited, multiple pages regenerated in a consistent state — this is what the tool is for.

The rest of this guide builds on this sample, walking through the pieces needed to write sources for your own project.

## Source structure

There are four kinds of sources.

- **Schema** — A single file that declares the types of structured data.
- **Content** — The actual data. Two kinds:
  - **Structured data** — YAML written according to the schema. A collection of records of the same shape (member lists, product lists, screen definitions, ...).
  - **Prose** — Text written directly in Markdown. No user-defined schema needed (structured by the tool's built-in schema).
- **Query** — Creates a view that reshapes structured data into a more convenient form for reference.
- **Template** — A file describing the shape of the final output page. References data or query results.

Details on each in [Schema and content](#schema-and-content), [Queries](#queries), and [Templates](#templates). For the order of writing and how to verify, see the next chapter, [Workflow](#workflow).

## Workflow

You don't have to wait until the templates are complete to see anything. At every stage — when only the schema is written, only the content is written, only the queries are written — pages showing "what you've written so far" are auto-generated on every build. These are the `__`-prefixed directories you saw in Quick Start.

In the table below, "where to write" paths are relative to the project directory (`<project>/`), and "where to check" paths are relative to the output directory (`.another-mood/<project>/`).

| Stage | What you write | Where to write | Where to check |
|---|---|---|---|
| 1 | Schema | `definition/schema.yaml` | `output/__db/__entity_defs/<entity>.md` |
| 2 | Content | `contents/**/*.yaml` (structured data)<br>`contents/**/*.md` (prose) | `output/__db/__entity_data/<entity>.md` |
| 3 | Query | `definition/queries/**/*.yaml` | `output/__db/__queries/<query>.md` |
| 4 | Template | `definition/templates/**/*.md` | `output/default/index.md` and below |

Schema and content are required; queries are optional; templates are required for the final output. `schema.yaml` is the only fixed single file — everything else can be freely split across multiple files and subdirectories. To change paths, see [CLI](reference/cli.md).

With `mood watch` running, the output of each stage updates in the browser as you edit. By the time you start writing templates, the shapes of the data and query results they reference are already settled, so you can focus on the templates. Syntax errors in your sources show up in the browser through the same mechanism, and you watch and fix them as you go — this "write, check, fix" loop is what the workflow looks like in practice.

### When to use `mood build` vs `mood watch`

- `mood watch` — Start it and leave it running when you want to edit and watch results live in the browser (i.e., while a human is actively writing).
- `mood build` — Use this for one-shot generation in automated build pipelines, or when an agent (Claude Code, etc.) is running an "edit → check build status → next edit" loop.

The deciding factor: whether errors are read by a human or picked up by a machine. `watch` is for humans to see errors in the console or browser and fix them inline. `build` finishes and returns a result (success or failure), so automated pipelines or agents can act on the result and continue.

## Schema and content

### Structured data — declare the schema first

Member lists, product lists, screen definitions, order histories — kinds of data where many records share the same shape go in **content files** (`contents/*.yaml`). Before writing them, declare the shape in the **schema file** (`definition/schema.yaml`).

Data without a schema declaration causes a build error. Likewise, writing mistakes (missing required fields, type mismatches, undeclared fields) are caught at build time and stop the build. The intent is to prevent broken data from flowing downstream (to queries and templates) without the writer noticing.

Schemas are written in **JSON Schema** (for the supported vocabulary and minor differences from the original spec, see [Schema](reference/schema.md)). A sample schema file:

```yaml
type: object
additionalProperties: false
properties:
  members:
    type: object
    additionalProperties:        # ← means "map of same-shaped entries"
      type: object
      additionalProperties: false
      properties:
        name: { type: string }
        role: { type: string }
      required: [name, role]
```

A content file matching this schema (the file name is up to you):

```yaml
members:
  alice:
    name: Alice
    role: engineer
  bob:
    name: Bob
    role: engineer
```

The root structure is fixed and always satisfies these three rules:

- The outermost type is `type: object`
- Each entry under `properties:` represents one **entity** (a collection of records of the same shape) — `members` in the example above
- `additionalProperties: false` (written immediately above `properties:`) makes any undeclared top-level key an error

The entity name (`members`) must match the top-level key in the content file.

There are three standard patterns for the body of each entity (the value under `properties`): multiple records as a map, multiple records as an array, and a single record enumerated by `properties`. Each is covered below.

#### Multiple records — write as a map

The `members` example above uses this pattern. Put the value type under `additionalProperties` in the schema, and write the content file as a map (key-value pairs). When you have many records of the same shape, this **map pattern** is almost always the right choice. Repeating the schema excerpt and content file:

```yaml
# definition/schema.yaml — entity excerpt
members:
  type: object
  additionalProperties:
    type: object
    additionalProperties: false
    properties:
      name: { type: string }
      role: { type: string }
    required: [name, role]
```

```yaml
# content file
members:
  alice:
    name: Alice
    role: engineer
  bob:
    name: Bob
    role: engineer
```

At build time this is **normalized** to an array (the map you wrote becomes an array), and the map keys (`alice`, `bob`) are added to each record as an `id` field. From templates it appears as:

```yaml
members:
  - { id: alice, name: Alice, role: engineer }
  - { id: bob,   name: Bob,   role: engineer }
```

The `id` field can be referenced from both templates and queries. As shown in the workflow table, you can verify the result via `output/__db/__entity_defs/<entity>.md` (how the tool interpreted the declared type) and `output/__db/__entity_data/<entity>.md` (whether the data is being loaded as expected).

There are two reasons to write as a map. First, even as the number of records grows, the YAML data stays more readable than the array form (each record's `id` comes first and acts like a heading). Second, `id` uniqueness is enforced at YAML parse time — duplicate keys raise a parse error immediately, so you don't discover later that two records had the same `id`.

#### Multiple records — write as an array

Conversely, if you don't need those two advantages (readability and ID uniqueness), you can write the entity as an array (an ordered sequence) using `type: array`. Examples: procedures where only the order matters, a sequence of annotations not referenced individually from elsewhere, or a stream of records too trivial to bother assigning IDs.

```yaml
# definition/schema.yaml — entity excerpt
steps:
  type: array
  items:
    type: object
    additionalProperties: false
    properties:
      label: { type: string }
    required: [label]
```

```yaml
# content file
steps:
  - label: Boil water
  - label: Add tea leaves
  - label: Wait 3 minutes
```

Unlike the map pattern, no normalization happens; the array you wrote is passed to templates as-is.

#### Single record — enumerate keys via `properties`

For things like site config — where the keys are known up front and there is exactly one record — list the keys under `properties` rather than `additionalProperties`:

```yaml
# add to definition/schema.yaml
site_config:
  type: object
  additionalProperties: false
  properties:
    title: { type: string }
    base_url: { type: string }
```

```yaml
# content file
site_config:
  title: My Site
  base_url: https://example.com
```

Like the array form, no normalization happens; the value is passed to templates as written.

#### When to nest vs split into a separate entity

A child collection can sit either nested inside its parent, or split off into a separate top-level entity. The rule of thumb is **does the child still make sense if the parent is gone?**

- If no (composition) → nest. Inner `additionalProperties` are normalized recursively at every level.
- If yes (aggregation) → declare the child as a separate top-level entity and reference it by key.

```yaml
# Composition — buttons live inside their screen record
screens:
  user-screen:
    title: User screen
    buttons:
      save:
        label: Save
        action: save
      cancel:
        label: Cancel
        action: cancel

# Aggregation — orders reference customers that live on their own
customers:
  tanaka:
    name: Tanaka Taro
orders:
  order-001:
    title: Order A
    customer: tanaka       # references a customer by id (declared with x-ref in the schema)
```

For aggregation, declare the relationship with [`x-ref`](reference/schema.md#entity-references-x-ref).

#### Content files — naming and layout are up to you

As we've seen, the data contents must follow the JSON Schema constraints from the schema file. The organization of the content files themselves (filenames, directory structure, number of files), however, has no such constraints. Organize at whatever granularity fits the project — by domain, by chapter, by review unit, and so on:

- Subdirectories are fine
- Filenames and directory names need not match entity names
- A single file may contain data for multiple entities
- Data for a single entity may be split across multiple files

At build time all YAML files are merged.

### Prose — write directly in Markdown

While data with many records of the same shape is written as structured data in YAML, **longer-form prose that doesn't fit a fixed shape** is awkward to express in YAML. Explanatory text, background, supplementary notes, FAQs, guides, help articles — content you'd rather just write directly in Markdown.

For this kind of prose, you don't declare a schema — just place a `.md` file under `contents/`. The **tool's built-in schema** is applied implicitly (the YAML example below shows the concrete shape).

For example, say you write `contents/guides/ordering.md` like this:

```markdown
# Ordering flow

Add items to your cart and proceed to checkout...
```

From templates, records appear in an array under the **reserved name `prose`**:

```yaml
prose:
  - id: guides/ordering          # file's relative path (without extension)
    title: Ordering flow         # the first H1
    body:                        # the file's full Markdown
      mime_type: text/markdown
      content: |
        # Ordering flow

        Add items to your cart and proceed to checkout...
```

One file = one record, and the three fields `id` / `title` / `body` are defined by the built-in schema. How to embed `body.content` is covered in detail in the [Templates](#templates) chapter.

## Queries

A query is a mechanism that reshapes structured data into a more convenient form for reference. The result becomes a named **view** that templates can reference the same way as structured data. Add queries as needed.

Typical situations for writing a query: grouping (by category, by role, ...), selecting or renaming fields, or reusing the same transformed result across multiple templates.

### Example: grouping by role

An example query from the member-list sample. The source data (the `members` array normalized in the [Schema and content](#schema-and-content) chapter) looks like this:

```yaml
members:
  - { id: alice, name: Alice, role: engineer }
  - { id: bob,   name: Bob,   role: engineer }
  - { id: carol, name: Carol, role: designer }
```

A query that groups it by `role`:

```yaml
# definition/queries/by_role.yaml
by_role:                  # ← the file's top-level key becomes the view name
  from: members           # source data
  grouped:
    by: role              # grouping key
  select:
    - item: role
      as: id              # output role as the id field
    - item: role
    - item: members
```

This produces the view `by_role`. From templates it appears as:

```yaml
by_role:
  - id: engineer
    role: engineer
    members:
      - { id: alice, name: Alice, role: engineer }
      - { id: bob,   name: Bob,   role: engineer }
  - id: designer
    role: designer
    members:
      - { id: carol, name: Carol, role: designer }
```

### Anatomy of a query

A query has seven blocks: `from` → `flatten` (optional) → `join` (optional) → `where` (optional) → `grouped` (optional) → `select` (optional) → `sort` (optional).

| Block | Role |
|---|---|
| `from` | Specifies the source data by entity name. |
| `flatten` | Unwinds an array attribute — one input row produces N output rows where N is the array length. |
| `join` | Attaches matching rows from another entity onto each input row. |
| `where` | Filters records by a predicate (e.g. `{ active: true }`). |
| `grouped` | Combines records that share the same value for the field named by `by`. |
| `select` | Lists fields to include in the output. Use `as` to rename. |
| `sort` | Orders the output records by one field (e.g. `{ by: name }`). |

File names and splitting under `definition/queries/` are as flexible as for content files: multiple views per file and subdirectories are both allowed.

For full syntax and examples, see [Query](reference/query.md).

## Templates

Templates are the mechanism for shaping data and views into custom-formatted pages. The notation combines the syntax of [Jinja2](https://jinja.palletsprojects.com/) — the template engine this tool builds on — with the tool's own additions (custom filters such as `link`, and the `{% mood_view %}` tag for splitting output across files).

### Jinja2 basics

At a minimum, know these:

- `{{ x }}` — embed a value
- `{{ x | f }}` — pass the value through a **filter** before embedding; Another Mood adds its own filters (such as `link`) to Jinja2's built-ins
- `{% for x in xs %}...{% endfor %}` — loop
- `{% if x %}...{% endif %}` — branch
- `{# ... #}` — comment

For the full syntax, see the [Jinja2 official docs](https://jinja.palletsprojects.com/).

Templates render with whitespace trimming on, so a control tag alone on its line leaves no blank line in the output. See [Template — Whitespace](reference/template.md#whitespace) for how tag indentation and blank lines carry through.

### Root template

`definition/templates/index.md` is the site's entry point — the root template. The template engine begins evaluation here. Write the body of the home page along with the `{% mood_view %}` calls that generate subpages.

Sample `definition/templates/index.md`:

```jinja2
# Project Members

## Members

{% for member in members %}
{% mood_view "member.md" with member %}
- {{ member | link }}
{% endfor %}

## By Role

{% for entry in by_role %}
{% mood_view "by_role.md" with entry %}
- {{ entry | link }}
{% endfor %}
```

Each loop does two things per record: it **writes that record's subpage** and **emits an index link** to it. The sections below take the machinery apart: writing subpages, the subtemplates that render them, where the pages land, and the `link` that points at them.

### Subpages: the `{% mood_view %}` tag

`{% mood_view "TEMPLATE_NAME.md" with DATA %}` evaluates `definition/templates/TEMPLATE_NAME.md` against `DATA`, and writes the result to its own file when `DATA`'s type is listed in `definition/reports.yaml` (the sample lists every type shown here). A type that isn't listed expands in place instead.

When it writes a separate file, `{% mood_view %}` inserts **nothing** into the page it appears on — everything it renders goes into that file. So each pass through the loop writes one subpage elsewhere and adds one bullet link to this page.

For the full tag specification, see [Template — `mood_view`](reference/template.md#mood_view).

### Subtemplates

Templates called by `{% mood_view %}`. The record passed in via `with` — the **subject** — has its fields available directly as top-level variables:

```jinja2
{# definition/templates/member.md #}
# {{ name }}

Role: {{ role }}
```

The subject is also bound as `this`, so `{{ this.name }}` is the same as `{{ name }}`.

A subtemplate can itself call `{% mood_view %}`, so a subpage can generate further subpages of its own.

### Where subpages land

A subpage mirrors the record's place in the data, under `default/`: its path is the record's address in the data — like `/members/alice` — with `.md` appended. So the `members` entity's records become `default/members/alice.md` and so on, and the `by_role` query's groups (given an `id` by the `as: id` trick from the queries chapter) become `default/by_role/engineer.md`. You can check each record's address in `__db/__entity_data/` and `__db/__queries/`, where it appears as `_anchor_path`.

A record only gets a subpage of its own if its type is listed in `definition/reports.yaml` — that listing is what grants it a page (see [Reports](reference/reports.md)); the sample project already lists both `members` records and `by_role` groups.

### Linking to subpages: the `link` filter

Look again at the pair of lines inside the sample's loops:

```jinja2
{% mood_view "member.md" with member %}
- {{ member | link }}
```

`{{ member | link }}` turns the record into a Markdown link to that record — here landing at the top of the very subpage the `{% mood_view %}` above it has just written. The URL is built from the record's address — the same one that just decided where the subpage lands — and the relative path is worked out for you, so you never hand-write `members/{{ member.id }}.md`. For the rest of the linking toolkit, see the [Template reference](reference/template.md).

The pairing is a convenience, not a rule — links and `{% mood_view %}` calls can live in separate loops when a page calls for a different arrangement (the [music sample](../showcase/music/) does this).

### Embedding a Markdown body

The `body` field of a prose record holds two subfields, `mime_type` and `content`. To embed the body in a template, pipe `.content` through [`relink`](reference/template.md#relink) — it emits the Markdown as-is and resolves any `node:` cross-references the body links to:

```jinja2
{# embed the prose body #}
{{ body.content | relink }}
```

For details, see [Schema — Built-in schema: prose](reference/schema.md#built-in-schema-prose).

### Undefined fields become the empty string

```jinja2
| {{ member.id }} | {{ member.metadata.title }} |
```

If `metadata` is absent — or is present but lacks `title` — neither raises an error; both yield the **empty string**.

Be aware that misspellings silently produce empty strings — no error is raised. While writing, check the actual data in `__db/__entity_data/` and the shape of query results in `__db/__queries/` ([Workflow](#workflow)).

## Further reading

- [Reference](reference/index.md) — syntax, full options, and reserved names for each feature.
- [showcase/music/](../showcase/music/) — a more complex working sample than the member list, modeling a fictional music catalog (artists, albums, tracks, labels, genres, playlists) that exercises groupings, joins, multi-join chains, intrinsic flatten, self-referencing entities, and prose alongside structured data.
