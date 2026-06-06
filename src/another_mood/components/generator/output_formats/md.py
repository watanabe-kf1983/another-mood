"""`md` OutputFormat — see design/generator/output-format-spec.md."""

import re

from markupsafe import Markup

from another_mood.components.generator.template_engine import OutputFormat
from another_mood.components.generator.url import url_escape

# CommonMark renders any escaped ASCII punctuation identically to the
# unescaped form, so a blanket escape is invisible in the output and
# prevents accidental syntax (heading / emphasis / table / code / HTML).
_MD_ESCAPE_PATTERN = re.compile(r"([!-/:-@\[-`{-~])")

_BACKTICK_RUN_PATTERN = re.compile(r"`+")


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


def _longest_backtick_run(text: str) -> int:
    return max((len(run) for run in _BACKTICK_RUN_PATTERN.findall(text)), default=0)


MD = OutputFormat(
    name="md",
    escape=md_escape,
    globals={
        "code_inline": code_inline,
        "code_fenced": code_fenced,
    },
    filters={
        "in_cell": in_cell,
        "as_url": as_url,
    },
)
