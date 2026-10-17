"""Blocking checks on the Release-Highlight trailer of a pull request body.

Run by the pr-lint workflow rather than by ``make ci``: the input exists only
on a pull request. Standard library only, so the workflow needs no install
step. Reads ``PR_BODY``, reports every defect as an error annotation, and
publishes the kinds the body declares as the step output ``kinds``.

Recognition is anchored to the start of a line, exactly like the release-time
collection grep — a line the collection would miss is a line this check refuses
to read. That symmetry is also the escape hatch: an indented example is
invisible to both, which is how a body can quote the format without declaring
anything.
"""

import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

TRAILER_KEY = "Release-Highlight"
KINDS = ("breaking", "feature", "fix")

# Matched with fullmatch against a right-stripped line, so these patterns need
# no anchors. A trailer the release-time grep would collect, and nothing else:
_TRAILER = re.compile(rf"{re.escape(TRAILER_KEY)}: (?P<kind>{'|'.join(KINDS)})")
# Near misses: a wrong key spelling, a wrong kind, a missing space. Deliberately
# narrow, and matched as a prefix — it has to stay clear of prose that merely
# mentions these words.
_LOOKALIKE = re.compile(r"release[-_ ]?(?:highlight|note)s?[ \t]*:", re.IGNORECASE)
# Each explanation section belongs to a group of kinds, and the two have to
# appear together so the release notes can file the section under its kind.
_BREAKING_HEADING = re.compile(r"##[ \t]+breaking change", re.IGNORECASE)
_HIGHLIGHT_HEADING = re.compile(r"##[ \t]+release highlight", re.IGNORECASE)
_HIGHLIGHT_KINDS = frozenset({"feature", "fix"})


def main() -> int:
    body = os.environ.get("PR_BODY", "")
    defects = trailer_defects(body)
    for defect in defects:
        print(f"::error::{defect}")

    publish_step_output("kinds", " ".join(sorted(declared_kinds(body))))
    return 1 if defects else 0


def trailer_defects(body: str) -> Sequence[str]:
    """Everything about the trailer this body gets wrong, in reading order."""
    lines = _stripped_lines(body)
    kinds = _declared_kinds_in(lines)
    return (
        *_malformed_trailers(lines),
        *_breaking_section_mismatch(lines, kinds),
        *_orphan_highlight_section(lines, kinds),
    )


def declared_kinds(body: str) -> frozenset[str]:
    """The kinds the release-time collection would read out of this body."""
    return _declared_kinds_in(_stripped_lines(body))


def publish_step_output(name: str, value: str) -> None:
    """Hand a value to the later workflow steps; a no-op off the runner."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file is None:
        return

    with Path(output_file).open("a", encoding="utf-8") as output:
        output.write(f"{name}={value}\n")


def _stripped_lines(body: str) -> Sequence[str]:
    """Lines without their trailing whitespace, CRLF bodies included."""
    return tuple(line.rstrip() for line in body.splitlines())


def _declared_kinds_in(lines: Sequence[str]) -> frozenset[str]:
    return frozenset(
        match["kind"] for line in lines if (match := _TRAILER.fullmatch(line))
    )


def _malformed_trailers(lines: Sequence[str]) -> Sequence[str]:
    return tuple(
        f"Malformed {TRAILER_KEY} trailer: {line!r}. Write exactly "
        f"'{TRAILER_KEY}: <{' | '.join(KINDS)}>' at the start of a line, or "
        f"indent the line by four spaces to quote the format without declaring it."
        for line in lines
        if _LOOKALIKE.match(line) and not _TRAILER.fullmatch(line)
    )


def _breaking_section_mismatch(
    lines: Sequence[str], kinds: frozenset[str]
) -> Sequence[str]:
    """A break and its migration summary come together, in either direction."""
    has_section = _has_heading(lines, _BREAKING_HEADING)
    declares_break = "breaking" in kinds
    if has_section and not declares_break:
        return (
            f"This body has a '## Breaking change' section but no "
            f"'{TRAILER_KEY}: breaking' trailer. Add the trailer at the end of the "
            f"body, or, if nothing breaks, retitle the section "
            f"'## Release highlight' and declare feature or fix.",
        )
    elif declares_break and not has_section:
        return (
            f"This body declares '{TRAILER_KEY}: breaking' but has no "
            f"'## Breaking change' section. A break goes out with a summary of "
            f"the migration and a pointer to its steps under docs/; write them "
            f"under that heading.",
        )
    else:
        return ()


def _orphan_highlight_section(
    lines: Sequence[str], kinds: frozenset[str]
) -> Sequence[str]:
    """A highlight section settles the intent; the flag cannot then be absent."""
    if kinds & _HIGHLIGHT_KINDS or not _has_heading(lines, _HIGHLIGHT_HEADING):
        return ()
    else:
        return (
            f"This body has a '## Release highlight' section but no feature or "
            f"fix trailer, so the release notes have nowhere to file it. Add "
            f"'{TRAILER_KEY}: <feature | fix>' at the end of the body. If the "
            f"section describes a break, retitle it '## Breaking change'.",
        )


def _has_heading(lines: Sequence[str], heading: re.Pattern[str]) -> bool:
    return any(heading.fullmatch(line) for line in lines)


if __name__ == "__main__":
    sys.exit(main())
