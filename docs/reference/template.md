# Template

A **template** is the presentation layer that turns data and views into Markdown documents. The notation is [Jinja2](https://jinja.palletsprojects.com/) — see the official docs for the base syntax — plus the tool's own additions, all of which are listed here:

| Addition | Kind | Purpose |
|---|---|---|
| [`mood_view`](#mood_view) | tag | render a subtemplate, as its own page or inline |
| [`link`](#link) | filter | Markdown link to a node |
| [`href`](#href) | filter | the URL targeting a node, alone |
| [`label`](#label) | filter | the display text for a node, alone |
| [`anchor`](#anchor) | filter | emit a node's link target (`<a id>`) |
| [`node`](#node) | function | resolve an anchor path to its node |
| [`child`](#child) | filter | step from a node to one of its children |
| [`in_cell`](#in_cell) | filter | insert a value into a Markdown table cell |
| [`code_inline`](#code_inline) | function | wrap a value in a Markdown code span |
| [`code_fenced`](#code_fenced) | function | wrap a value in a Markdown fenced code block |
| [`as_url`](#as_url) | filter | percent-encode a hand-written link URL |
| [`under_heading`](#under_heading) | filter | shift an embedded fragment's headings to nest under a heading |
| [`relink`](#relink) | filter | resolve a prose body's `node:` links to their targets |

Two evaluation rules also differ from stock Jinja2: [accessing an undefined name renders as the empty string](#handling-undefined-access), and [every substituted value is Markdown-escaped](#markdown-escaping).

## Template files

Templates are placed under `{project}/definition/templates/` with the `.md` extension. The `.md` extension is chosen so editors apply Markdown syntax highlighting to the body — template syntax and Markdown body are mixed, and treating files as plain text makes them visually hard to distinguish.

`definition/templates/index.md` is the **root template**. The template engine begins evaluation here; every other template is rendered by a [`mood_view`](#mood_view) call reachable from it.

```jinja2
{# templates/index.md #}
# Product Catalog

## Products

{% for product in products %}
{% mood_view "product-detail.md" with product %}
- {{ product | link }}
{% endfor %}
```

## Template context

From templates, you can reference both entity data declared in [Schema](schema.md) and views defined by [Query](query.md) in the **same namespace**.

- Entities: keys under `properties` in schema.yaml
- Query views: top-level keys within files under `definition/queries/`
- Prose view (`prose`): auto-generated from Markdown files under `contents/` (see [Schema — Built-in schema: prose](schema.md#built-in-schema-prose))

```jinja2
{# `products` is a structured-data entity, `bestsellers` is a query view #}
{% for product in products %}
  ...
{% endfor %}

{% for entry in bestsellers %}
  ...
{% endfor %}
```

A subtemplate additionally sees its subject — the data passed to the `mood_view` call that rendered it — as `this` and as spread top-level variables ([Subtemplate side](#subtemplate-side)).

## Linking

A link names a node — a record, a query group, a singleton, a nested object — and resolves to wherever that node is rendered. The [`link`](#link) / [`href`](#href) / [`anchor`](#anchor) filters build it for you; this section is the model they rest on.

### Where a node is rendered

A link lands in-page only where the node's [`anchor`](#anchor) (`<a id>`) sits, and an anchor is placed in one of two ways:

**On a subject, automatically.** Every template render opens with its subject's anchor — for the root template that subject is the data root, for a [`mood_view`](#mood_view) subtemplate it is the node passed to it. A link to a subject lands where it renders: the top of its own page when split, or its place in the page when inline.

**On any other node, by hand.** A node a template only refers to — shown in a table, linked in a list — is not a subject, so it carries no anchor until the author adds one with `| anchor`.

### Building the link

[`link`](#link) / [`href`](#href) return the URL pointing at the node's [`anchor`](#anchor). A node with no anchor of its own still resolves to its nearest ancestor's page, so the link lands nearby rather than nowhere.

### Anchor paths

The node a link points at is often not in the template's context — a foreign key, a related record. To reach it, you look it up by its **anchor path**: the node's address in the data tree, built from the keys and record `id`s on the way to it (`/members/alice` is the record `alice` of `members`). [`node`](#node) does the lookup, resolving an anchor path — usually from plain segments, not a written-out string — to its node, ready to link:

```jinja2
{# product.category_id is just an id; the category node is elsewhere in the tree #}
{{ node("categories", product.category_id) | link }}
```

A path matching no node is a **missing node**, kept visible rather than a dead link. The `__entity_data/` and `__queries/` diagnostics record each node's anchor path as `_anchor_path` — percent-encoded, so a `/` or space inside a segment value appears there as `%2F` / `%20` (letters, including non-ASCII, stay readable).

## Tags

### `mood_view`

A custom tag that renders a subtemplate, **either as its own page (split) or expanded in place (inline)**.

```jinja2
{% mood_view "NAME" with DATA %}
```

| Part | Description |
|---|---|
| `NAME` | The subtemplate's filename including the extension (e.g. `"product-detail.md"`), given as a string. |
| `DATA` | The subject passed to the subtemplate. |

#### Split vs inline

Whether the subtemplate becomes its own page or expands in place is driven by [`file_per`](reports.md): if the subject's [type ID](reports.md#type-ids) is listed there, the subtemplate is **split** into its own file; otherwise it expands **inline** at the call site (like `{% include %}`). The same template therefore works either way — list the type in `file_per` for a multi-page (web) build, omit it for a single-page build.

A *split* subject must be an addressable node, so a scalar raises an error; inline expansion accepts any value.

#### Output path

A split page's path mirrors where the subject sits in the data: it is the subject's [anchor path](#anchor-paths) with `.md` appended, written under `reports/`. A record with anchor path `/products/foo` is written to `reports/products/foo.md`; a singleton at `/overview`, to `reports/overview.md`.

Two pages that resolve to the same path make the build fail rather than silently overwrite one another.

#### Return value of the tag

When the subject is **split**, the tag **returns the empty string**: the output file is written as a side effect, so nothing appears at the position where `{% mood_view %}` was placed in the parent template (a tag alone on its line emits nothing under block trimming — see [Whitespace](#whitespace)). When **inline**, the tag returns the rendered text, which appears at the call site.

To link from a parent page to a subpage, emit the link as a separate expression — typically a `{{ node | link }}` next to the `{% mood_view %}` call:

```jinja2
{% for product in products %}
{% mood_view "product-detail.md" with product %}
- {{ product | link }}
{% endfor %}
```

The subpage opens with the subject's own anchor automatically ([Linking](#where-a-node-is-rendered)), so this link lands on it — you write no `| anchor` for a `mood_view` subject.

#### Subtemplate side

The subject passed via `with` is always bound under the fixed name `this`, so a subtemplate can reach the subject itself regardless of its type.

When the subject is a **map**, its fields are *also* spread as top-level variables, so bare access keeps working — `{{ name }}` and `{{ this.name }}` are equivalent.

```jinja2
{# templates/product-detail.md — map subject #}
# {{ name }}

{{ description }}

| Field | Value |
|------|-----|
{% for spec in specs %}
| {{ spec.label }} | {{ spec.value }} |
{% endfor %}
```

When the subject is a **list**, there are no fields to spread, so iterate `this`:

```jinja2
{# templates/product-list.md — list subject #}
{% for product in this %}
- {{ product.name }}
{% endfor %}
```

## Filters

The Jinja2 built-in `| safe` is covered under [Markdown escaping](#markdown-escaping).

### `child`

`parent | child(seg)` steps from a resolved node to one of its children: for an array, `seg` is a record's `id`; for a mapping, a key. It is the relative counterpart to [`node`](#node)'s absolute lookup — reach for it when you already hold the parent node, instead of respelling the parent's whole path.

```jinja2
{# track.genre_id references a record in the `genres` array #}
{{ genres | child(track.genre_id) | link }}
```

A `seg` that matches no child resolves to a **missing node**, kept visible exactly as [`node`](#node)'s.

### `link`

`node | link` renders a Markdown link to the node — the display text per [`label`](#label), the URL per [`href`](#href):

```jinja2
{{ member | link }}
```

renders `[Alice](members/alice.md#/members/alice)`. An optional argument overrides the display text: `{{ member | link("the author") }}`.

To link a node other than the one at hand, resolve it first with [`node`](#node):

```jinja2
{{ node("members", member.id) | link }}
```

For a [missing node](#node), the display text in brackets — `[text]` with no URL — so the broken reference stays visible rather than becoming a link to nowhere.

### `href`

`node | href` renders the URL alone — a relative path to the target, ready to drop into a link you write by hand:

```
members/alice.md#/members/alice      (from the root page)
../members/alice.md#/members/alice   (from a by_role/… page)
```

How that URL lands — and the page-level fallback when the node has no anchor — is covered under [Building the link](#building-the-link). For a [missing node](#node), `href` renders the empty string.

### `label`

`node | label` renders the display text alone: the node's `title`, `name`, or `id` — the first field present — falling back to its anchor path. For a [missing node](#node), the attempted anchor path.

```jinja2
[{{ entity | label }} (ER diagram)]({{ entity | href }})
```

### `anchor`

`node | anchor` emits the node's link target — `<a id="…">` carrying the node's anchor path — at the point it is written. It is the receiving end of [`href`](#href): the URL `href` builds for a node arrives at this `<a id>`.

```jinja2
{{ member | anchor }}
```

emits `<a id="/members/alice"></a>`.

Use `| anchor` to give a node a landing spot where you render it — a child node shown in a table row or list item, say — so links to it arrive there. A [`mood_view`](#mood_view) subject gets one [automatically](#where-a-node-is-rendered) and needs none. For a [missing node](#node), `anchor` emits nothing.

### `in_cell`

`value | in_cell` inserts `value` into a Markdown table cell, turning newlines into `<br>` so the row stays on one source line.

```jinja2
| Name | Description |
|------|-------------|
| {{ product.name | in_cell }} | {{ product.description | in_cell }} |
```

### `as_url`

`value | as_url` inserts `value` as the URL of a Markdown link. Pass the unencoded URL; `as_url` percent-encodes what needs encoding (spaces, parentheses, etc.) but leaves non-ASCII letters and punctuation readable.

Links between pages never need it — [`link`](#link) / [`href`](#href) produce ready-to-use URLs. Reach for `as_url` when the URL itself comes from data or is written by hand, such as an external link:

```jinja2
[{{ site.label }}]({{ site.url | as_url }})
```

### `dedent`

`{% filter dedent %}…{% endfilter %}` strips the common leading whitespace from the block's rendered text, so you can indent the block's body — tags and content alike — for readability and have that shared indentation removed from the output:

```jinja2
{% filter dedent %}
    {% for row in rows %}
        - {{ row.name }}
    {% endfor %}
{% endfilter %}
```

It removes only the *common* minimum, so lines nested deeper than their siblings keep the difference. That fully flattens a block whose emitted lines sit at one level; for uneven nesting it suits whitespace-insensitive output (e.g. a Mermaid diagram) rather than significant-whitespace Markdown such as list or table rows.

### `under_heading`

`value | under_heading("##")` shifts the headings in an embedded Markdown fragment down so they nest under an enclosing heading. The argument is that enclosing level *as you see it at the call site* — a run of `#` — so every heading in the fragment moves down by that many levels: a fragment's own `#` title becomes `###`, nesting as a subsection directly under the `## …` heading above it. Levels never exceed `######` (H6), so a fragment shifted past the bottom collapses onto it.

Use it as a block filter wrapping embedded output, or piped on a prose body:

```jinja2
## Members

{% filter under_heading("##") %}
{% mood_view "member.md" with member %}
{% endfilter %}

{{ body.content | under_heading("##") }}
```

Only the fragment's own top-level headings move. A heading quoted inside a blockquote or nested in a list item, a setext heading (the `===` / `---` underline style), and `#` inside a code fence are all left untouched. Like the other Markdown-emitting filters here, it inserts its result as-is — no `| safe` needed.

### `relink`

`body | relink` resolves the `node:` links in a prose body to working URLs. A prose body refers to another node by linking to its [anchor path](#anchor-paths) under the `node:` scheme — `[text](node:/anchor/path)` — and `relink` rewrites each to the same relative URL [`link`](#link) would build for that node:

```jinja2
{{ prose.body.content | relink }}
```

This is the standard way to embed a prose body: it emits the Markdown as-is (no [escaping](#markdown-escaping), like the other Markdown-emitting filters here — so no `| safe`) and resolves any cross-references it carries. Link resolution is its only job, so compose it with [`under_heading`](#under_heading) to also nest the body's headings under an enclosing one:

```jinja2
{{ prose.body.content | relink | under_heading("##") }}
```

Only inline links are rewritten; a `node:` written inside a code span or fence is left untouched. An unresolved `node:` reference drops its destination and keeps the link text as a conspicuous `[text]`, the same as [`link`](#link) for a [missing node](#node).

## Functions

### `node`

`node(*segs, path=None)` resolves an anchor path to its node, ready for [`link`](#link) / [`href`](#href) / [`label`](#label):

```jinja2
{# inside a by_role group: this member copy lives at /by_role/…, but the
   member's own page is at /members/{id} #}
{{ node("members", member.id) | link }}
```

**Positional segments** are raw values: one argument is one path segment, percent-encoded so a `/` inside a value does not split it into two segments. This is the common form.

**`path=`** takes a complete, ready-made anchor path and uses it exactly as written — not encoded. Use it for constant paths, and for `prose` records — their `id` is a relative file path whose `/` must stay a separator:

```jinja2
{{ node(path="/prose/design/architecture") | link }}
{{ node(path="/overview") | link("About this site") }}
```

The two compose: `path=` is a verbatim prefix and the positional segments are percent-encoded and appended, so you can take a ready-made path and dig into its children — `node("y", path="/prose/x")` resolves `/prose/x/y`.

A path that matches no node resolves to a **missing node** rather than raising an error; the rendering filters keep it visible — [`link`](#link) brackets the attempted path as `[text]`, [`href`](#href) renders the empty string — so you can spot the broken reference and fix the source.

### `code_inline`

`code_inline(value)` wraps `value` in a Markdown code span. Handles any value, including one containing backticks.

```jinja2
| {{ column.name }} | {{ code_inline(column.type) }} |
```

emits `` `VARCHAR(16)` `` for `VARCHAR(16)`, and `` `` `nested` `` `` for `` `nested` ``.

### `code_fenced`

`code_fenced(value, language="")` wraps `value` in a Markdown fenced code block. `language` is the language tag on the opening fence (`yaml`, `python`, `mermaid`, …). Handles any value, including one containing ` ``` `.

```jinja2
{{ code_fenced(snippet.source, snippet.language) }}
```

Use this for code blocks whose body comes from data — including Mermaid diagrams whose source is held in data:

```jinja2
{{ code_fenced(diagram.source, "mermaid") }}
```

## Whitespace

Templates render with Jinja2 block trimming on (`trim_blocks` + `lstrip_blocks`): a control tag alone on its line — `{% for %}`, `{% if %}`, `{% set %}`, `{% mood_view %}` and their `end…` partners — emits nothing, so neither its indentation nor its trailing newline reaches the output. You can indent such tags to show nesting without affecting the result, but the content lines between them are emitted verbatim — leading whitespace included — so they cannot be indented the same way. The literal blank lines you leave in the template are the ones that survive into the Markdown.

To indent a block's body — tags and content together — and strip that indentation back out of the output, wrap it in the [`dedent`](#dedent) filter (best where the output tolerates leftover indentation, such as a Mermaid diagram).

To keep whitespace around a specific tag, opt out per-tag with a `+`: `{%+ if x %}` keeps the leading indentation, and `{% endif +%}` keeps the trailing newline — useful when an inline `{% if %}…{% endif %}` ends a content line and its line break must be preserved.

## Handling undefined access

Accessing an undefined variable or attribute inside a template does not raise an error; it renders as the empty string. Chained attribute access (e.g., `spec.metadata.title`) also yields the empty string when any intermediate key is missing.

So, when referencing optional attributes, guards like `if metadata is defined` are unnecessary:

```jinja2
{# safe even when metadata or metadata.title is absent #}
| {{ spec.id }} | {{ spec.metadata.title }} |
```

Note that misspellings are also silently rendered as empty strings — no error is raised. While writing, verify the actual data via `__entity_data/` and the shape of query results via `__queries/`.

## Markdown escaping

Substituted values can contain characters that look like Markdown syntax. A `|` inside a value will split a table column; an `_` can flip the rest of a line into italics; a leading `#` can promote a value to a heading. To prevent such accidents, the template engine backslash-escapes every ASCII punctuation character emitted from a `{{ expr }}` substitution.

The escape is invisible in the rendered output. Markdown renders backslash-escaped ASCII punctuation as the original character (`\_` displays as `_`, `\|` as `|`, and so on), so the final page is identical to what you'd get without the escape — minus the accidental syntax. Only the emitted Markdown source picks up the backslashes.

Given `product.name = "Acme | Pro"`, this template:

```jinja2
| Name |
|------|
| {{ product.name }} |
```

emits the Markdown source:

```
| Name |
|------|
| Acme \| Pro |
```

which renders as a one-cell table containing the literal text `Acme | Pro`.

### When to use `| safe`

The escape backfires inside Markdown's verbatim regions — places where Markdown reproduces the content as-is and does **not** strip backslashes:

- Inline code spans: `` `…` ``
- Fenced code blocks: ` ```…``` `

A substitution `{{ column.type }}` whose value is `VARCHAR(16)` emits `VARCHAR\(16\)`. Outside a verbatim region that renders fine. Inside one, the backslashes show through to the reader.

Mermaid blocks (` ```mermaid `) are a fenced code block whose content is then parsed by the Mermaid renderer, which has its own syntax and rejects stray backslashes outright. Missing `| safe` shows up here not as visible `\` in the page but as a `Syntax error in text` placeholder where the diagram should be.

To skip the escape inside a verbatim region, append `| safe`.

Inline code span:

```jinja2
| {{ column.name }} | `{{ column.type | safe }}` |
```

Mermaid block:

````jinja2
```mermaid
classDiagram
class {{ entity.id | safe }}
```
````

Outside the verbatim regions above, `| safe` is unnecessary and only adds source noise.

### Position-aware helpers

A few Markdown positions need handling that the default escape alone cannot provide — table cells need `<br>` for newlines, link URLs need percent-encoding, code spans and fences need to handle backticks inside the value. Four of the built-in additions exist for these positions:

| Position | What goes wrong with the default substitution | Helper |
|---|---|---|
| Table cell | a value with newlines splits the row | [`in_cell`](#in_cell) |
| Inline code span | `\` becomes visible inside `` `…` `` | [`code_inline`](#code_inline) |
| Fenced code block | `\` becomes visible; a value containing ` ``` ` closes the fence early | [`code_fenced`](#code_fenced) |
| Hand-written link URL | the URL isn't percent-encoded | [`as_url`](#as_url) |

For inline code spans and fenced code blocks, `code_inline` / `code_fenced` are an alternative to the `| safe` recipe above. Reach for the helpers when the value comes from data and may contain stray backticks; `| safe` only works if you can trust the value verbatim.
