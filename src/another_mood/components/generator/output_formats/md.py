"""The ``md`` output format: escape, markdown helpers, and anchor link filters."""

# ``_meta`` is a template-public node field under the reserved ``_`` prefix
# (see data_tree.py), not a Python-protected attribute.
# pyright: reportPrivateUsage=false

import re
import textwrap
from collections.abc import Callable, Mapping
from urllib.parse import urlsplit

from minijinja import pass_state
from minijinja._lowlevel import State
from markupsafe import Markup

from another_mood.components.generator.data_tree import Node, is_blob
from another_mood.components.generator.data_tree_filters import (
    MissingNode,
    node_href,
    node_label,
)
from another_mood.components.generator.output_formats.heading_shift import (
    under_heading as _under_heading,
)
from another_mood.components.generator.edition import PagingPolicy
from another_mood.components.generator.omitted import OMITTED
from another_mood.components.shared.markdown import parse, rewrite_inline_links
from another_mood.components.generator.template_engine import (
    OutputFormat,
    as_template_helper,
)
from another_mood.components.generator.url import url_escape

# CommonMark renders any escaped ASCII punctuation identically to the
# unescaped form, so a blanket escape is invisible in the output and
# prevents accidental syntax (heading / emphasis / table / code / HTML).
_MD_ESCAPE_PATTERN = re.compile(r"([!-/:-@\[-`{-~])")

_BACKTICK_RUN_PATTERN = re.compile(r"`+")

# Scheme name a prose body's inline links use to point at a node (the `node` in
# `node:/path`, sans the `:` separator — see `relink`).
_NODE_SCHEME = "node"


def md_escape(text: str) -> str:
    return _MD_ESCAPE_PATTERN.sub(r"\\\1", text)


def code_inline(text: str) -> Markup:
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


def code_fenced(text: str, language: object = "") -> Markup:
    # An absent `language` only shapes the output, so it means the same as an
    # unpassed one: no language tag, and the block itself still renders.
    tag = "" if language is None else language
    # CommonMark requires >=3 backticks for a fenced block, and the opening
    # fence must be longer than any backtick run in the body to avoid early
    # termination. `\` is literal inside, so the body is not escaped.
    fence = "`" * max(3, _longest_backtick_run(text) + 1)
    # Closing fence needs its own line — guarantee a trailing newline.
    body = text if text.endswith("\n") else text + "\n"
    return Markup(f"{fence}{tag}\n{body}{fence}")


def dedent(text: str) -> Markup:
    """Strip the *common* leading whitespace from a rendered block.

    Lets a template indent a ``{% filter dedent %}`` block for readability and
    have that shared indentation removed from the output.  Keys off the common
    minimum (``textwrap.dedent``), so lines nested deeper than their siblings
    keep the difference.  Owned by the format because indentation only matters
    where output whitespace is significant (Markdown), like ``trim_blocks`` /
    ``lstrip_blocks``.
    """
    # Markup so finalize does not escape the block a second time: every
    # interpolation inside it already went through finalize on its way in.
    return Markup(textwrap.dedent(text))


def under_heading(text: str, marker: str) -> Markup:
    """Filter adapter for :func:`.heading_shift.under_heading`.

    An absent ``marker`` is left to raise: it names the enclosing heading level,
    and without it there is no shift to apply.
    """
    # Markup so finalize does not re-escape the shifted Markdown (already valid
    # output, like the other markdown-emitting helpers here).
    return Markup(_under_heading(text, marker))


def in_cell(text: str) -> Markup:
    # Escape table-structure characters (`|` in particular), then turn
    # embedded newlines into `<br>` — a raw newline would split the row
    # across source lines. Markup-returned so finalize doesn't re-escape
    # the `<br>` we just emitted.
    return Markup(md_escape(text).replace("\n", "<br>"))


def as_url(text: str) -> Markup:
    # Keep URL-structural punctuation raw so the link survives, but escape
    # `(` `)` by leaving them out of `safe` — raw, they would close the
    # Markdown link target `[...](...)` early.
    encoded = url_escape(text, safe=":/?#[]@!$&'*+,;=")
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
    lands.  Emits nothing where there is no landing to stamp.
    """
    if isinstance(a, Node) and a._meta.stamps_anchor:
        # anchor_path is IRI-escaped (`"` / `<` / `>` percent-encoded), so it
        # is safe raw in a quoted attribute; Markup keeps finalize from
        # backslash-escaping it.  Closed element, so it cannot swallow
        # following inline text.
        return Markup(f'<a id="{a._meta.anchor_path}"></a>')
    else:
        return Markup("")


def stamp_anchor(rendered: str, subject: object) -> str:
    """Stamp the subject node's anchor at the top of its rendered output.

    A render is the one point where the system knows a node is drawn here, so
    it drops the ``| anchor`` landing point automatically (split page: top;
    inline: the spot). A subject whose :func:`md_anchor` emits nothing is
    returned untouched; otherwise the anchor gets a trailing newline so it
    cannot glue onto a following heading.
    """
    anchor = md_anchor(subject)
    if not anchor:
        return rendered
    return f"{anchor}\n{rendered}"


def _longest_backtick_run(text: str) -> int:
    return max((len(run) for run in _BACKTICK_RUN_PATTERN.findall(text)), default=0)


def make_link_filters(
    paging: PagingPolicy, node_map: Mapping[str, Node]
) -> Mapping[str, Callable[..., Markup | None]]:
    """The markdown link filters, bound to ``paging`` and the build's node map:
    ``href`` / ``link`` / ``anchor`` render a resolved node, and ``relink``
    rewrites a prose body's inline ``node:`` destinations.

    An unresolved reference never renders a link to a dead URL: ``href`` yields
    empty, while ``link`` and ``relink`` both leave a conspicuous bracketed
    ``[text]`` — ``link`` brackets the escaped display text, ``relink`` drops the
    destination from the source ``[text](node:…)``.
    """

    # `href` / `link` / `relink` take `@pass_state` to read the source page from
    # the render state's `this` — a relative URL depends on the page it is
    # written on. `anchor` needs no state (its id is the node's own
    # page-independent anchor path), so it stays the bare `md_anchor`. Only
    # `relink` touches `node_map` — it resolves anchor-path strings itself; the
    # others receive an already-resolved node.
    @pass_state
    def href(state: State, a: object) -> Markup | None:
        if a is None:
            return None
        if isinstance(a, MissingNode):
            return Markup("")
        # Markup so finalize does not corrupt the URL (see `as_url`).
        return Markup(node_href(paging, state.lookup("this"), a))

    @pass_state
    def link(state: State, a: object, text: object = OMITTED) -> Markup | None:
        if a is None:
            return None
        if text is OMITTED:
            display = node_label(a)
        elif text is None:
            # An absent display text empties the text slot alone: the reference
            # resolved, so dropping the whole link would make a display-side gap
            # cost the addressing that is still good.
            display = ""
        else:
            display = str(text)
        if isinstance(a, MissingNode):
            # A broken reference is left as a conspicuous bracketed `[text]`,
            # never a `[..](..)` to a dead URL — the same shape `relink` leaves
            # a dropped `node:` destination, so both broken-link forms read alike.
            return Markup(f"[{md_escape(display)}]")
        return md_link(display, node_href(paging, state.lookup("this"), a))

    @pass_state
    def relink(state: State, value: object) -> Markup | None:
        if value is None:
            return None
        source = state.lookup("this")

        def resolve(href: str) -> str | None:
            parts = urlsplit(href)
            if parts.scheme != _NODE_SCHEME:
                return href  # not a `node:` link: keep it unchanged
            anchor_path = (
                f"{parts.path}#{parts.fragment}" if parts.fragment else parts.path
            )
            target = node_map.get(anchor_path)
            if target is not None:
                # The node itself — a prose heading is one too, keyed by its
                # full `path#slug`, so it resolves here without a special case.
                return node_href(paging, source, target)
            elif parts.fragment:
                # Missed with a `#fragment`: only a blob — whose URL is a bare,
                # fragmentless file path — can carry a raw author fragment (a
                # PDF's `#page=3`). Every other base already owns its landing
                # fragment, so re-attach only onto a blob; anything else is
                # unresolved and drops (the conspicuous bracketed `[text]`,
                # never leaking `node:`).
                base_target = node_map.get(parts.path)
                if base_target is not None and is_blob(base_target):
                    return f"{node_href(paging, source, base_target)}#{parts.fragment}"
                else:
                    return None
            else:
                # Missed with no fragment to carry — simply unresolved.
                return None

        return Markup(rewrite_inline_links(parse(str(value)), resolve))

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
# Each is a text processor above, wrapped for the render boundary: the subject
# arrives coerced, and an absent one never reaches it (`as_template_helper`).
MD_GLOBALS: Mapping[str, Callable[..., Markup | None]] = {
    "code_inline": as_template_helper(code_inline),
    "code_fenced": as_template_helper(code_fenced),
}
MD_FILTERS: Mapping[str, Callable[..., Markup | None]] = {
    "in_cell": as_template_helper(in_cell),
    "as_url": as_template_helper(as_url),
    "dedent": as_template_helper(dedent),
    "under_heading": as_template_helper(under_heading),
}
