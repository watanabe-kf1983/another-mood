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
- [{{ product.name }}](product-detail/{{ product.id }}.md)
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
- Mermaid blocks (` ```mermaid `): the fence's content is handed to the Mermaid renderer, which has its own syntax and does not understand Markdown escapes

A substitution `{{ column.type }}` whose value is `VARCHAR(16)` emits `VARCHAR\(16\)`. Outside a verbatim region that renders fine. Inside one, the backslashes show through to the reader (or worse, break the Mermaid parser).

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

## Jinja2 extension: `mood_view`

`{% mood_view %}` is a custom tag that renders a subtemplate and **writes the result to a separate file**.

```jinja2
{% mood_view "NAME" with DATA %}
```

| Part | Description |
|---|---|
| `NAME` | The subtemplate's filename including the extension (e.g. `"product-detail.md"`), given as a string. |
| `DATA` | The data passed to the subtemplate (a map object). |

An error is raised if `DATA` is not a map.

### Automatic output path

The output path is determined by whether `DATA` has an `id` field.

| `DATA` | Output (when `NAME` is `"product-detail.md"`) |
|---|---|
| Includes `{ id: "foo", ... }` | `{outDir}/product-detail/foo.md` |
| No `id` field | `{outDir}/product-detail.md` |

### Return value of the tag

The `{% mood_view %}` tag itself **returns the empty string**. The output file is written as a side effect, so nothing appears at the position where `{% mood_view %}` was placed in the parent template (just whitespace).

To link from a parent page to a subpage, write Markdown link syntax separately, outside the `{% mood_view %}` call:

```jinja2
{%- for product in products %}
- [{{ product.name }}](product-detail/{{ product.id }}.md)
{%- endfor %}

{%- for product in products -%}
{% mood_view "product-detail.md" with product %}
{%- endfor %}
```

### Subtemplate side

Inside a subtemplate, the fields of the map passed via `with` are accessible as top-level variables.

```jinja2
{# templates/product-detail.md #}
# {{ name }}

{{ description }}

| Field | Value |
|------|-----|
{% for spec in specs -%}
| {{ spec.label }} | {{ spec.value }} |
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
