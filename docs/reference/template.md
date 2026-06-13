# Template

A **template** is the presentation layer that turns data and views into Markdown documents. The notation is [Jinja2](https://jinja.palletsprojects.com/) — see the official docs for the base syntax — plus the tool's own additions, all of which are listed here:

| Addition | Kind | Purpose |
|---|---|---|
| [`mood_view`](#mood_view) | tag | render a subtemplate and write the result as its own page |
| [`link`](#link) | filter | Markdown link to a node's page |
| [`href`](#href) | filter | the URL of a node's page, alone |
| [`label`](#label) | filter | the display text for a node, alone |
| [`node`](#node) | function, filter | resolve an anchor path to its node |
| [`in_cell`](#in_cell) | filter | insert a value into a Markdown table cell |
| [`code_inline`](#code_inline) | function | wrap a value in a Markdown code span |
| [`code_fenced`](#code_fenced) | function | wrap a value in a Markdown fenced code block |
| [`as_url`](#as_url) | filter | percent-encode a hand-written link URL |

Two evaluation rules also differ from stock Jinja2: [accessing an undefined name renders as the empty string](#handling-undefined-access), and [every substituted value is Markdown-escaped](#markdown-escaping).

## Template files

Templates are placed under `{project}/definition/templates/` with the `.md` extension. The `.md` extension is chosen so editors apply Markdown syntax highlighting to the body — template syntax and Markdown body are mixed, and treating files as plain text makes them visually hard to distinguish.

`definition/templates/index.md` is the **root template**. The template engine begins evaluation here; every other template is rendered by a [`mood_view`](#mood_view) call reachable from it.

```jinja2
{# templates/index.md #}
# Product Catalog

## Products

{%- for product in products %}
{%- mood_view "product-detail.md" with product %}
- {{ product | link }}
{%- endfor %}
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

## Anchor paths

Every node in the data — a record, a query group, a singleton, a nested object — has an **anchor path**: its address in the data tree, built from the keys and record `id`s on the way to it. `/members/alice` is the record `alice` of the `members` entity; `/by_role/engineer/members/alice` is the copy of that record sitting inside a `by_role` group. The `__table_view/` and `__meta_query/` diagnostics show each node's anchor path as `_anchor_path`.

Anchor paths drive both ends of a link: a node's page is written at its anchor path ([Output path](#output-path)), and the linking filters resolve an anchor path back to a node and render a link to it ([`node`](#node), [`link`](#link)) — URLs between pages never need to be written by hand.

## Tags

### `mood_view`

A custom tag that renders a subtemplate and **writes the result to a separate file**.

```jinja2
{% mood_view "NAME" with DATA %}
```

| Part | Description |
|---|---|
| `NAME` | The subtemplate's filename including the extension (e.g. `"product-detail.md"`), given as a string. |
| `DATA` | The subject passed to the subtemplate — a map (a record) or a list (a collection). |

An error is raised if `DATA` is a scalar (neither a map nor a list).

#### Output path

A split page's path mirrors where the subject sits in the data: it is the subject's [anchor path](#anchor-paths) with `.md` appended, written under `reports/`. A record with anchor path `/products/foo` is written to `reports/products/foo.md`; a singleton at `/overview`, to `reports/overview.md`.

To split a node into its own page, list its ObjectType ID in [`file_per`](reports.md). Two pages that resolve to the same path make the build fail rather than silently overwrite one another.

#### Return value of the tag

The `{% mood_view %}` tag itself **returns the empty string**. The output file is written as a side effect, so nothing appears at the position where `{% mood_view %}` was placed in the parent template (just whitespace, which the surrounding whitespace-control dashes normally trim).

To link from a parent page to a subpage, emit the link as a separate expression — typically a `{{ node | link }}` next to the `{% mood_view %}` call:

```jinja2
{%- for product in products %}
{%- mood_view "product-detail.md" with product %}
- {{ product | link }}
{%- endfor %}
```

#### Subtemplate side

The subject passed via `with` is always bound under the fixed name `this`, so a subtemplate can reach the subject itself regardless of its type.

When the subject is a **map**, its fields are *also* spread as top-level variables, so bare access keeps working — `{{ name }}` and `{{ this.name }}` are equivalent.

```jinja2
{# templates/product-detail.md — map subject #}
# {{ name }}

{{ description }}

| Field | Value |
|------|-----|
{% for spec in specs -%}
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

#### The `inline` option

Adding `inline` after `with DATA` causes the subtemplate's result to **not be written to a separate file**; instead it expands inline at the call site (similar to `{% include %}`).

```jinja2
{% mood_view "NAME" with DATA inline %}
```

Use this when the default `{% mood_view %}` behavior (separate-file output) would scatter multiple sections across separate pages, but you want them collected into a single page.

## Filters

`node` can also be piped as a filter; it is documented under [Functions](#functions). The Jinja2 built-in `| safe` is covered under [Markdown escaping](#markdown-escaping).

### `link`

`node | link` renders a Markdown link to the node's page — the display text per [`label`](#label), the URL per [`href`](#href):

```jinja2
{{ member | link }}
```

renders `[Alice](members/alice.md#/members/alice)`. An optional argument overrides the display text: `{{ member | link("the author") }}`.

To link a node other than the one at hand, resolve it first with [`node`](#node):

```jinja2
{{ node("members", member.id) | link }}
```

For an unresolved target, `link` renders the display text alone with no link around it (for an unresolved `node()`, the attempted path), keeping the broken reference visible on the page.

### `href`

`node | href` renders the URL alone: the relative path from the current page to the page the target lands on, plus the target's anchor path as the URL fragment.

```
members/alice.md#/members/alice      (from the root page)
../members/alice.md#/members/alice   (from a by_role/… page)
```

The fragment is always appended, even when the target is the page's own root. A node without a page of its own yields the page it is inlined into, with the fragment addressing the node there. For an unresolved target, `href` renders the empty string.

### `label`

`node | label` renders the display text alone: the node's `title`, `name`, or `id` — the first field present — falling back to its anchor path. For an unresolved target, the attempted anchor path.

```jinja2
[{{ entity | label }} (ER diagram)]({{ entity | href }})
```

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

## Functions

### `node`

`node(seg, *segs)` builds an anchor path from segments and resolves it to its node, ready for [`link`](#link) / [`href`](#href) / [`label`](#label):

```jinja2
{# inside a by_role group: this member copy lives at /by_role/…, but the
   member's own page is at /members/{id} #}
{{ node("members", member.id) | link }}
```

One argument is one path segment. Each segment is escaped, so a `/` inside a value does not act as a separator.

A single argument that starts with `/` is instead taken as a complete, ready-made anchor path and used verbatim. Use this form for constant paths, and for `prose` records — their `id` is a relative file path whose `/` must stay a separator:

```jinja2
{{ node("/prose/design/architecture") | link }}
{{ node("/overview") | link("About this site") }}
```

`node` also works as a filter: `{{ "/prose/index" | node | link }}`.

A path that matches no node resolves to a **missing node** rather than raising an error; the rendering filters keep it visible — [`link`](#link) renders the attempted path as plain text, [`href`](#href) the empty string — so you can spot the broken reference and fix the source.

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

## Handling undefined access

Accessing an undefined variable or attribute inside a template does not raise an error; it renders as the empty string. Chained attribute access (e.g., `spec.metadata.title`) also yields the empty string when any intermediate key is missing.

So, when referencing optional attributes, guards like `if metadata is defined` are unnecessary:

```jinja2
{# safe even when metadata or metadata.title is absent #}
| {{ spec.id }} | {{ spec.metadata.title }} |
```

Note that misspellings are also silently rendered as empty strings — no error is raised. While writing, verify the actual data via `__table_view/` and the shape of query results via `__meta_query/`.

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
