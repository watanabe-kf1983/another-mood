"""`md` OutputFormat — see design/generator/output-format-spec.md."""

import re
from urllib.parse import quote

from markupsafe import Markup

from another_mood.components.generator.template_engine import OutputFormat

# CommonMark renders any escaped ASCII punctuation identically to the
# unescaped form, so a blanket escape is invisible in the output and
# prevents accidental syntax (heading / emphasis / table / code / HTML).
_MD_ESCAPE_PATTERN = re.compile(r"([!-/:-@\[-`{-~])")

_BACKTICK_RUN_PATTERN = re.compile(r"`+")


def md_escape(text: str) -> str:
    return _MD_ESCAPE_PATTERN.sub(r"\\\1", text)


def code_inline(value: object) -> Markup:
    text = str(value)
    fence = "`" * (_longest_backtick_run(text) + 1)
    # CommonMark strips one space from each side of a space-bounded code-span
    # body (unless it is entirely spaces), so the padding is invisible but
    # lets the content start/end with a backtick or be all-whitespace.
    needs_pad = text.startswith("`") or text.endswith("`") or text.strip() == ""
    body = f" {text} " if needs_pad else text
    return Markup(f"{fence}{body}{fence}")


def code_fenced(value: object, language: str = "") -> Markup:
    text = str(value)
    fence = "`" * max(3, _longest_backtick_run(text) + 1)
    body = text if text.endswith("\n") else text + "\n"
    return Markup(f"{fence}{language}\n{body}{fence}")


def in_cell(value: object) -> Markup:
    return Markup(md_escape(str(value)).replace("\n", "<br>"))


def as_url(value: object) -> Markup:
    # Safe set = RFC 3986 gen-delims + sub-delims minus `(` `)`, which would
    # otherwise close the Markdown link target prematurely.
    encoded = quote(str(value), safe=":/?#[]@!$&'*+,;=")
    return Markup(encoded.replace("(", "%28").replace(")", "%29"))


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
