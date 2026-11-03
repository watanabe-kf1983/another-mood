# Template

Behavior kept on purpose, outside the contract of `docs/reference/template.md`. The stage name in this chapter (`normalize_contents`) is that of the [stage table of the internal structure](../20-internal/20-pipeline.md#stages). The boundary of what templates are allowed is in [Trust Model](70-trust-model.md); editions, output paths, and the placement of the colophon page are in [Reports](60-reports.md).

Terms used in this chapter:

- **entity / record** — the set of records of the same shape that the schema declares, and one of them ([Schema](30-schema.md)). The types written in `file_per` are the contract's Type IDs
- **node** — a point in the data tree that can be the target of a link. A record, an array of records, a view row, a singleton (a single object), a nested object, a prose heading (Linking in `docs/reference/template.md`)
- **anchor path** — a node's address. The route from the root of the data tree, written as a `/`-separated string. ASCII reserved characters are percent-encoded (Anchor paths, same document)
- **prose / blob** — the built-in entities for the Markdown files and the other files in `contents/`. The id is the file's relative path ([Schema](30-schema.md#prose)). All files are merged into one tree before being passed downstream (same Schema chapter)
- **subject** — what one template render draws. For the root template, the root of the tree; for a `render` subtemplate, the node passed to it. Visible from the template as `this`
- **`render`** — the filter written `{{ node | render("sub.md") }}` that draws a subtemplate with a changed subject (`render`, same document)
- **split / inline** — whether the subject is written out as a separate page or expanded at the call site. Decided by `file_per` (Split vs inline, same document)
- **link helpers** — `node()` is the function that looks a node up by address; `child` is the filter that steps one level down from a parent node. `link` / `href` / `label` draw the node they are given as a link, a URL, or a display name, and `anchor` places the landing spot `<a id>`. `relink` resolves the `node:` links in a body (Filters / Functions, same document)
- **author / user** — [Role terms](../index.md#role-terms)
- **`node:`** — the notation for writing an anchor path as a link target in a prose body (`[text](node:/members/alice)`). Besides the author writing it, `normalize_contents` converts the body's relative links to this notation ([Schema](30-schema.md#relative-links-become-node-a-fragment-within-the-same-page-is-not-converted))
- **`under_heading`** — the filter that demotes the headings of embedded Markdown by one level. The representative of the filters that emit Markdown
- **finalize / `Markup`** — finalize is the escape gate that a `{{ }}` value passes just before being written to the output. `Markup` is a string marked as already escaped, which passes through finalize untouched. Helpers that emit Markdown return `Markup`
- **missing value** — the absence of a value. Expressed in the data model by omitting the key ([JSON data model](../20-internal/30-communication/10-json-data-model.md))
- **broken reference** — a reference that was resolved and missed: `node()` or a `node:` in a body pointing where nothing is
- **build info / colophon** — build info is the set of facts about one run. Templates pull them one at a time with `build_info(key, default)` (`build_info` in `docs/reference/template.md`). The colophon is the page `__build_info/` that tabulates all of it
- **tap** — a term of [CLI](10-cli.md#tap)

## Language

### The vocabulary is closed to filters, tests, operators, and registered functions; values have no methods

The contract says that Python methods such as `.startswith()` are unavailable (No Python methods on values). What is kept behind it is that the set of vocabulary reachable from a template can be written out in full in docs.

The vocabulary is the filters, tests, and operators from Jinja2, plus the functions the tool registers (`node`, `code_inline`, and so on), all of which can be enumerated in docs.

minijinja has `pycompat`, which grows the methods of Python strings, lists, and dicts onto values, but it is switched off. Which methods of which Python version are available cannot be pinned down, and upstream positions it as a shim for migrating from Jinja2.

With the vocabulary closed to this set, the set that can be written in docs and the set reachable from a template coincide, and a boundary the user can be guided to can be drawn.

### The author's Python helpers are not accepted

There is no mechanism for registering project-specific Python helpers, such as auto-loading `filters.py` or entry points.

The person who wrote a project and the person who runs `mood build` on it are not necessarily the same. Allowing arbitrary Python means that building a distributed project runs arbitrary code on a third party's machine. It is the same shape as Excel macros, and the damage lands on the receiving side. This boundary is covered by [Trust Model](70-trust-model.md).

The demand for formatting is met by the Jinja2-derived built-in filters that minijinja implements and by this tool's helpers. If a gap appears, it is filled by declarative extension (additions to the DSL, pre-shaping on the data side), never by way of arbitrary Python execution.

### A missing value draws nothing, and is no error

Trying to draw a missing key yields empty output, and so does a chain with a gap in the middle (`a.b.c`) (Handling undefined access in the contract). This is obtained by setting minijinja's `undefined_behavior` to `chainable`.

The default `lenient` is a half-measure that silently passes the first level and errors on chains. `strict` makes you write a guard every time you read an attribute that is optional in the schema.

Helpers behave the same. Passing a missing value through a filter or function invents no representation such as `"None"`; it draws nothing.

When an argument that builds the address for `node()` or `child` is missing, the reference itself does not come into being, so it is not even a broken reference, and nothing is drawn. Drawing nothing is safer than dropping the missing argument and resolving to a different address.

This rule is what makes the JSON data model's convention "a nullable item omits the key rather than holding a value" hold. If a missing value were an error, the author could not omit keys and would write null, and the premise that the data model has no null would collapse.

A broken reference is treated separately. A reference that was resolved and missed becomes a conspicuous `[text]` ([An unresolved reference is made conspicuous as `[text]`](#an-unresolved-reference-is-made-conspicuous-as-text)). A missing optional value is a normal case the convention admits, so it is not made conspicuous.

## Shape of the output

### Position-aware helpers are named for the position; those that build syntax are functions, those that normalize content are filters

The running-text escape is correct only in running text; code spans, fenced blocks, table cells, and link URLs each need their own normalization (Position-aware helpers in the contract). Helpers come in two forms:

- **Functions that build syntax** (`code_inline` / `code_fenced`). The width of the delimiter has to depend on the content, and an author writing a fixed number of backticks breaks on arbitrary input, so the function builds the whole construct
- **Filters that normalize content** (`in_cell` / `as_url`). The author writes the delimiter, and the value placed inside is normalized for the position

Construction as a function and transformation as a filter follows the Jinja2 convention (`range` / `dict` are functions, `upper` / `urlencode` are filters).

The names `code_*` / `in_*` / `as_*` name the notion of a position, independent of Markdown. The same positions exist in other output formats. When a format is added, another implementation is registered under the same names, and templates are not rewritten.

## Page splitting

### A node is drawn on exactly one page, determined by its position in the data

Which page is decided by `render`'s splitting rule; where on the page is decided by the template. Link resolution stands on this. Because both ends of a link (the page that writes it and the page it points at) are derived from the node's position by the same rule, `link` / `href` / `relink` can relativize consistently.

So `render` raises a build error unless the subject it is given is a descendant of `this` (the condition the contract's `render` places on its `DATA` argument). Drawing a node outside the subtree of `this` inline makes the node's actual drawing position disagree with its page under the rule. Links from that node, computed from `this`, and links to it both break.

The judgment is structural (descendant or not), independent of split or inline and of which edition.

If the subject is split, it is drawn on its page under the rule and there is no harm, but whether it is split varies with the edition's `file_per`. To avoid the same call "passing in an edition that splits and being rejected in one that does not", a template's validity is decided by the template alone.

To draw a node from elsewhere, bring it into the subtree as a descendant through a query (join and the like), or refer to it with `| link`.

### Links from the parent are not made by `render`; the author writes them with `| link`

`render` does not emit a link from the parent to the split page automatically. A link is what `| link` does, adapting by itself to the URL of another page when split and to a `#fragment` on the same page when inline.

Giving it to `render` would be a double implementation, and the writing around the link, such as list markers, would leave the author's hands. `render`'s responsibility stays "where to put the content of this node".

### Inline is decided per type, not overridden at the call site

The intent to inline is expressed by leaving the type out of `file_per`. If a type in `file_per` could be forced inline at the call site, that node would be output twice, on its own page and in the inline body, and where `| link` points would disagree with where the thing is.

The reverse holds too: there is no way to force a type absent from `file_per` into a split at the call site. The intent to split is written in `file_per`.

### A heading has only an address within its record, and no `<a id>` is stamped

A prose heading is treated as a link target, with the address `<record's anchor path>#<slug>` (Anchor paths in the contract). In the data tree it is an element of the `headings` list, but the address folds the intermediate `headings` segment away. A heading is not a separate record; it has only a landing spot inside the record.

The subject's `<a id>` is stamped automatically by the rendering (Where a node is rendered in the contract), but not for headings. Markdown renderers (Goldmark, GitHub) put heading ids of their own, so stamping would duplicate the id. The `<slug>` of the address is made by the same rule as the renderer's id ([Schema](30-schema.md#heading-ids-are-github-compatible-slugs)), so the link lands on the renderer's id.

Ids the tool assembles from addresses (nodes other than headings) are stamped; ids made from heading text (headings) are left to the renderer. Placing `| anchor` by hand emits nothing for a heading.

### View row addresses are not guaranteed unique; only a collision when drawn as a page is stopped

Entity records have ids unique among siblings ([Schema](30-schema.md#unique-only-among-siblings)), checked after `normalize_contents` merges all files into one tree. View rows are given no such guarantee.

It cannot be guaranteed because a query's `flatten` clause splits one row into N. Keep the parent's id with a `select` clause and rows with the same id are bound to line up (`artist_album_pairs` in `showcase/music` takes this form under its intended usage).

A 1:1 projection, on the other hand, has valid addresses. So whether a view's rows duplicate cannot be decided by looking at the view definition.

So detection is deferred to the point where the address is actually used. Drawing duplicate rows as the subjects of pages makes the output paths collide, and the build stops (Output path in the contract).

Duplicates drawn within the same page are not detected. Two things happen. The `<a id>` is doubled, and links to the later row land on the earlier one. `node()` returns only the last row. In both, the landing point is a row of the same view with the same id, and the actual harm is small. Detecting and warning at construction time is not worth that harm.

## Anchor paths

### Non-ASCII stays raw, in IRI form

Anchor paths are treated as IRIs per RFC 3987. ASCII reserved characters and whitespace are percent-encoded, and the non-ASCII range the IRI permits (`ucschar`) stays raw (Anchor paths in the contract).

Percent-encoding everything would turn `/prose/書籍` into `/prose/%E6%9B%B8%E7%B1%8D`, and neither the `node:` addresses in bodies nor the `<a id>`s would be readable. Links and file names containing raw Unicode are valid in CommonMark, HTML, and the URL standard alike, and serialization to a URI is done by the consumer (Goldmark, browsers, static servers).

The set kept raw is the `ucschar` range rather than character categories (`\p{L}\p{N}`) because real ids such as `モーニング娘。` and `藤岡弘、` contain non-ASCII punctuation. The range is held by `shared/url.py`.

### Only the built-in prose and blob pass a `/` inside an id through

Addresses reserve `/` as the separator, so an id containing `/` is escaped to `%2F`. The exceptions are the built-in `prose` / `blob`. Their ids have structural hierarchy as paths relative to `contents/`, and both are flat array entities with no nesting, so reading everything after `prose/` as one id is unambiguous.

Escaping would produce unreadable addresses such as `prose/design%2Farchitecture`. They would also no longer match the `node:` derived from relative links the author writes in bodies with bare `/`.

This is not generalized to arbitrary ids containing `/`. The user's entities can change structure, so passing them through would let ambiguity creep in later.

## Links

### An unresolved reference is made conspicuous as `[text]`

When `node()` or a `node:` points where nothing is, no exception is thrown; the link is removed and the display text is wrapped in square brackets as `[text]` (`link` / `relink` in the contract).

Removing the link and leaving plain text would be indistinguishable from ordinary text that did resolve, and the failure would be buried in the output. `[text]` is a shortcut reference with no matching definition, which CommonMark renders brackets and all, so the broken reference stands out and the author notices and fixes it. `link` and `relink` are both aligned to this form.

### A `node:` in a body is resolved only in inline link form

Only the inline form `[text](node:…)` (including images, `![alt](node:…)`) is resolved. The reference form (`[text][label]` with a definition on another line), autolinks (`<node:…>`), and the form with a title (`[text](node:… "title")`) are not supported. This is a non-goal, not deferred work.

- The link normalization of `normalize_contents` generates only the inline form. The other forms appear only when handwritten, and rarely
- An autolink's display text is the URL. For the reference form, turning an unresolved one into `[text]` straddles the link position and the definition line and cannot be folded cleanly. Neither has demand worth the cost of support
- It is enough to tell authors "write handwritten `node:` references in inline form"

### `relink` is written explicitly by the author

`relink`, which replaces the `node:` in a body with relative URLs, is written by the author as `{{ prose.content | relink }}`. Having the system insert it implicitly is not adopted.

The only automatic hook that can be inserted per value is finalize, but finalize passes `Markup` through, and filters that emit Markdown, such as `under_heading`, return `Markup`. An implicit relink would stop firing the moment it was composed with `under_heading`, and `node:` would silently leak into the output.

Marking values as "not yet relinked" and propagating the mark is also unreliable, since the mark silently drops on string concatenation or conversion to Markup.

Explicit, the author places `relink` right next to the value that holds raw `node:`, which is reliable, and the composition order stays visible as `| relink | under_heading`.

## build_info

### Build info is read only by templates, and does not flow into the data layer

Build info is not made available as a system-defined entity that views can join. It is not put into the tap document either ([CLI](10-cli.md#the-document-holds-no-value-that-changes-from-run-to-run)).

If views could read it, a view's output would come to vary by machine and by run. Taking it away after authors have come to rely on it would break those views. Opening is easy and closing is a breaking change, so it is closed in advance. The reverse order, widening from the colophon into the data layer later, remains possible.

The line defended is not "determined by the sources alone" but "independent of the machine and of how it was started". The tap output already carries inventories the tool generates, such as `__definition`, and depends on the tool's version.

That build info must also reach the failure page (drawn with a built-in template) is another reason it cannot flow through the data layer ([promise of the internal structure](../20-internal/30-communication/index.md#build-info-travels-outside-the-data-flow)).
