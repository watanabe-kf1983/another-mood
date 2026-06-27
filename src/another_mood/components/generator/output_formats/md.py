"""The ``md`` output format: escape, markdown helpers, and anchor link filters."""

# ``_meta`` is a template-public node field under the reserved ``_`` prefix
# (see data_tree.py), not a Python-protected attribute.
# pyright: reportPrivateUsage=false

import re
import textwrap
from collections.abc import Callable, Mapping

from jinja2 import pass_context
from jinja2.runtime import Context
from markupsafe import Markup

from another_mood.components.generator.data_tree import Node
from another_mood.components.generator.data_tree_filters import (
    MissingNode,
    node_href,
    node_label,
)
from another_mood.components.generator.output_formats.heading_shift import (
    under_heading as _under_heading,
)
from another_mood.components.generator.reports_config import ReportsConfig
from another_mood.components.shared.markdown.inline_link import rewrite_inline_links
from another_mood.components.generator.template_engine import OutputFormat
from another_mood.components.generator.url import url_escape

# CommonMark renders any escaped ASCII punctuation identically to the
# unescaped form, so a blanket escape is invisible in the output and
# prevents accidental syntax (heading / emphasis / table / code / HTML).
_MD_ESCAPE_PATTERN = re.compile(r"([!-/:-@\[-`{-~])")

_BACKTICK_RUN_PATTERN = re.compile(r"`+")

# Scheme that a prose body's inline links use to point at a node (see `relink`).
_NODE_SCHEME = "node:"


def md_escape(text: str) -> str:
    return _MD_ESCAPE_PATTERN.sub(r"\\\1", text)


def code_inline(value: object) -> Markup:
    text = str(value)
    # n+1 backticks (n = longest run in body) so content can't close the
    # fence early. CommonMark 6.1: `\` is literal inside a code span — the
    # body is deliberately not escaped.
    fence = "`" * (_longest_backtick_run(text) + 1)
    # CommonMark strips one space from each side of a space-bounded code-span
    # body (unless it is entirely spaces), so the padding is invisible but
    # lets the content start/end with a backtick or be all-whitespace.
    needs_pad = text.startswith("`") or text.endswith("`") or text.strip() == ""
    body = f" {text} " if needs_pad else text
    return Markup(f"{fence}{body}{fence}")


def code_fenced(value: object, language: str = "") -> Markup:
    text = str(value)
    # CommonMark requires >=3 backticks for a fenced block, and the opening
    # fence must be longer than any backtick run in the body to avoid early
    # termination. `\` is literal inside, so the body is not escaped.
    fence = "`" * max(3, _longest_backtick_run(text) + 1)
    # Closing fence needs its own line — guarantee a trailing newline.
    body = text if text.endswith("\n") else text + "\n"
    return Markup(f"{fence}{language}\n{body}{fence}")


def dedent(text: str) -> str:
    """Strip the common leading whitespace from a rendered block.

    Registered as a filter so a template can indent the body of a
    ``{% filter dedent %}`` block — tags and content alike — for
    readability, then have that shared indentation removed from the
    output.  Owned by the format because, like ``trim_blocks`` /
    ``lstrip_blocks``, it only matters where output whitespace is
    significant (Markdown).  Keys off the *common* minimum
    (``textwrap.dedent``), so lines nested deeper than their siblings
    keep the difference: it fully flattens single-level blocks and
    suits whitespace-insensitive output (e.g. Mermaid) otherwise.
    """
    return textwrap.dedent(text)


def under_heading(value: object, marker: str) -> Markup:
    """Filter adapter for :func:`.heading_shift.under_heading`.

    The filter boundary is this format's concern, not the transform's: Jinja
    pipes in arbitrary values, so coerce to ``str``; the shifted Markdown is
    returned as Markup so the format's finalize hook does not re-escape it (it
    is already valid output, like the other markdown-emitting filters here).
    """
    return Markup(_under_heading(str(value), marker))


def in_cell(value: object) -> Markup:
    # Escape table-structure characters (`|` in particular), then turn
    # embedded newlines into `<br>` — a raw newline would split the row
    # across source lines. Markup-returned so finalize doesn't re-escape
    # the `<br>` we just emitted.
    return Markup(md_escape(str(value)).replace("\n", "<br>"))


def as_url(value: object) -> Markup:
    # Keep URL-structural punctuation raw so the link survives, but escape
    # `(` `)` by leaving them out of `safe` — raw, they would close the
    # Markdown link target `[...](...)` early.
    encoded = url_escape(str(value), safe=":/?#[]@!$&'*+,;=")
    # Markup-returned to bypass finalize (md_escape would inject backslashes
    # into the URL; Hugo treats those as literal and percent-encodes them to
    # %5C, corrupting the link).
    return Markup(encoded)


def md_link(display: str, url: str) -> Markup:
    # Escape the display text (the Markup return bypasses finalize); the url
    # is trusted as already URL-safe, so escaping it would corrupt it.
    return Markup(f"[{md_escape(display)}]({url})")


def md_anchor(a: object) -> Markup:
    """The receiving half of the link contract: an ``<a id>`` target carrying
    the node's anchor path, where the fragment that ``href`` always appends
    lands.

    The id reuses ``_meta.anchor_path`` verbatim — the same string ``node_href``
    puts in the fragment — so the two ends match by construction.  It is already
    IRI-escaped (``"`` / ``<`` / ``>`` are percent-encoded), so it is safe raw
    in a quoted attribute; the Markup return keeps finalize from backslash-
    escaping it.  The element is closed so it cannot swallow following inline
    content.  Only a node is anchored — a :class:`MissingNode`, or any non-node
    piped in, has no anchor path, so no ``href`` could ever target it and an
    anchor there would be unreachable; it emits nothing (mirroring ``href``).
    """
    if not isinstance(a, Node):
        return Markup("")
    return Markup(f'<a id="{a._meta.anchor_path}"></a>')


def stamp_anchor(rendered: str, subject: object) -> str:
    """Stamp the subject node's anchor at the top of its rendered output.

    A render is the one point where the system knows a node is drawn here, so
    it drops the ``| anchor`` landing point automatically (split page: top;
    inline: the spot). A non-node subject yields nothing and is returned
    untouched; a real node gets a trailing newline so its anchor cannot glue
    onto a following heading.
    """
    anchor = md_anchor(subject)
    if not anchor:
        return rendered
    return f"{anchor}\n{rendered}"


def _longest_backtick_run(text: str) -> int:
    return max((len(run) for run in _BACKTICK_RUN_PATTERN.findall(text)), default=0)


def make_link_filters(
    config: ReportsConfig, node_map: Mapping[str, Node]
) -> Mapping[str, Callable[..., object]]:
    """The markdown link filters, bound to ``config`` and the build's node map:
    ``href`` / ``link`` / ``anchor`` render a resolved node, and ``relink``
    rewrites a prose body's inline ``node:`` destinations.

    ``href`` / ``link`` / ``relink`` take ``@pass_context`` for two purposes: it
    reads the source page from the render context's ``this``, and it stops
    Jinja2's optimizer from constant-folding constant-argument calls — a
    compile-time-evaluated ``{{ node("/x") | href }}`` would bake one source
    page's relative URL into the compiled template and break the same template
    rendered from another page.  ``anchor`` needs neither (its id is the node's
    own page-independent anchor path), so it is the bare :func:`md_anchor`.

    An unresolved reference never renders a link to a dead URL: ``href`` yields
    empty, while ``link`` and ``relink`` both leave a conspicuous bracketed
    ``[text]`` — ``link`` brackets the escaped display text, ``relink`` drops the
    destination from the source ``[text](node:…)``.  Only ``relink`` needs
    ``node_map`` — it resolves anchor-path strings itself; the others receive a
    resolved node.
    """

    @pass_context
    def href(context: Context, a: object) -> Markup:
        if isinstance(a, MissingNode):
            return Markup("")
        # Markup so finalize does not corrupt the URL (see `as_url`).
        return Markup(node_href(config, context["this"], a))

    @pass_context
    def link(context: Context, a: object, text: object = None) -> Markup:
        display = str(text) if text is not None else node_label(a)
        if isinstance(a, MissingNode):
            # A broken reference is left as a conspicuous bracketed `[text]`,
            # never a `[..](..)` to a dead URL — the same shape `relink` leaves
            # a dropped `node:` destination, so both broken-link forms read alike.
            return Markup(f"[{md_escape(display)}]")
        return md_link(display, node_href(config, context["this"], a))

    @pass_context
    def relink(context: Context, value: object) -> Markup:
        source = context["this"]

        def resolve(href: str) -> str | None:
            if not href.startswith(_NODE_SCHEME):
                return href  # not a `node:` link: keep it unchanged
            target = node_map.get(href[len(_NODE_SCHEME) :])
            if target is None:
                # Unresolved: drop the destination, leaving the same conspicuous
                # bracketed `[text]` `link` leaves, never leaking `node:` to output.
                return None
            return node_href(config, source, target)

        return Markup(rewrite_inline_links(str(value), resolve))

    return {"href": href, "link": link, "anchor": md_anchor, "relink": relink}


MD = OutputFormat(
    name="md",
    escape=md_escape,
    # Markdown is whitespace-significant, so render with both block-trimming
    # options on.  lstrip_blocks drops the indentation before a line's `{% %}`
    # tag; trim_blocks drops the newline after it — together a control tag can
    # sit on its own indented line and emit nothing, so templates show their
    # structure plainly.  Templates are written for this regime: a tag that
    # must keep its surrounding whitespace opts out per-tag with `+`
    # (`{%+ if %}` / `{% if +%}`).
    trim_blocks=True,
    lstrip_blocks=True,
    post_process=stamp_anchor,
)

# The format's binding-free template helpers, for the caller to inject (the
# config / node-map-bound ones come from `make_link_filters`).
MD_GLOBALS: Mapping[str, Callable[..., object]] = {
    "code_inline": code_inline,
    "code_fenced": code_fenced,
}
MD_FILTERS: Mapping[str, Callable[..., object]] = {
    "in_cell": in_cell,
    "as_url": as_url,
    "dedent": dedent,
    "under_heading": under_heading,
}
