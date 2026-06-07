# Template

A **template** is the presentation layer that turns data and views into Markdown documents. It builds on [Jinja2](https://jinja.palletsprojects.com/) and adds the custom `{% mood_view %}` tag that controls file output.

Templates are placed under `{project}/definition/templates/` with the `.md` extension. The `.md` extension is chosen so editors apply Markdown syntax highlighting to the body — template syntax and Markdown body are mixed, and treating files as plain text makes them visually hard to distinguish.

## Entry point: `index.md`

`definition/templates/index.md` is the root template. The template engine begins evaluation here. Put the document-wide TOC (table of contents) in `index.md` and call subpages via `{% mood_view %}`.

```jinja2
{# templates/index.md #}
# Product Catalog

## Products

{%- for product in products %}
- [{{ product.name }}](products/{{ product.id }}.md)
{%- endfor %}

{%- for product in products -%}
{% mood_view "product-detail.md" with product %}
{%- endfor %}
```

## Data exposed to templates

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

## Jinja2 extension: `mood_view`

`{% mood_view %}` is a custom tag that renders a subtemplate and **writes the result to a separate file**.

```jinja2
{% mood_view "NAME" with DATA %}
```

| Part | Description |
|---|---|
| `NAME` | The subtemplate's filename including the extension (e.g. `"product-detail.md"`), given as a string. |
| `DATA` | The subject passed to the subtemplate — a map (a record) or a list (a collection). |

An error is raised if `DATA` is a scalar (neither a map nor a list).

### Automatic output path

A split page's path mirrors where the subject sits in the data: it is the subject's `_anchor_path` with `.md` appended, written under `reports/`. A record with `_anchor_path` `/products/foo` is written to `reports/products/foo.md`; a singleton at `/overview`, to `reports/overview.md`. Each node's `_anchor_path` is shown in the `__table_view/` and `__meta_query/` diagnostics.

To split a node into its own page, list its ObjectType ID in [`file_per`](reports.md). Two pages that resolve to the same path make the build fail rather than silently overwrite one another.

### Return value of the tag

The `{% mood_view %}` tag itself **returns the empty string**. The output file is written as a side effect, so nothing appears at the position where `{% mood_view %}` was placed in the parent template (just whitespace).

To link from a parent page to a subpage, write Markdown link syntax separately, outside the `{% mood_view %}` call:

```jinja2
{%- for product in products %}
- [{{ product.name }}](products/{{ product.id }}.md)
{%- endfor %}

{%- for product in products -%}
{% mood_view "product-detail.md" with product %}
{%- endfor %}
```

### Subtemplate side

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

### The `inline` option

Adding `inline` after `with DATA` causes the subtemplate's result to **not be written to a separate file**; instead it expands inline at the call site (similar to `{% include %}`).

```jinja2
{% mood_view "NAME" with DATA inline %}
```

Use this when the default `{% mood_view %}` behavior (separate-file output) would scatter multiple sections across separate pages, but you want them collected into a single page.

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

A few Markdown positions need handling that the default escape alone cannot provide — table cells need `<br>` for newlines, link URLs need percent-encoding, code spans and fences need to handle backticks inside the value. Another Mood ships four built-in helpers for these positions.

| Position | What goes wrong with the default substitution | Helper |
|---|---|---|
| Table cell | a value with newlines splits the row | `{{ value \| in_cell }}` |
| Inline code span | `\` becomes visible inside `` `…` `` | `{{ code_inline(value) }}` |
| Fenced code block | `\` becomes visible; a value containing ` ``` ` closes the fence early | `{{ code_fenced(value, "lang") }}` |
| Link URL | the URL isn't percent-encoded | `[label]({{ url \| as_url }})` |

For inline code spans and fenced code blocks, `code_inline` / `code_fenced` are an alternative to the `| safe` recipe above. Reach for the helpers when the value comes from data and may contain stray backticks; `| safe` only works if you can trust the value verbatim.

#### `value | in_cell`

Inserts `value` into a Markdown table cell, turning newlines into `<br>` so the row stays on one source line.

```jinja2
| Name | Description |
|------|-------------|
| {{ product.name | in_cell }} | {{ product.description | in_cell }} |
```

#### `code_inline(value)`

Wraps `value` in a Markdown code span. Handles any value, including one containing backticks.

```jinja2
| {{ column.name }} | {{ code_inline(column.type) }} |
```

emits `` `VARCHAR(16)` `` for `VARCHAR(16)`, and `` `` `nested` `` `` for `` `nested` ``.

#### `code_fenced(value, language="")`

Wraps `value` in a Markdown fenced code block. `language` is the language tag on the opening fence (`yaml`, `python`, `mermaid`, …). Handles any value, including one containing ` ``` `.

```jinja2
{{ code_fenced(snippet.source, snippet.language) }}
```

Use this for code blocks whose body comes from data — including Mermaid diagrams whose source is held in data:

```jinja2
{{ code_fenced(diagram.source, "mermaid") }}
```

#### `value | as_url`

Inserts `value` as the URL of a Markdown link. Pass the unencoded URL; `as_url` percent-encodes what needs encoding (spaces, parentheses, etc.) but leaves non-ASCII letters and punctuation readable.

```jinja2
[{{ link.label }}]({{ link.url | as_url }})
```
