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
_HIGHLIGHT_HEADING = re.compile(r"##[ \t]+release highlight", re.IGNORECASE)


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
    return (*_malformed_trailers(lines), *_orphan_highlight_section(lines))


def declared_kinds(body: str) -> frozenset[str]:
    """The kinds the release-time collection would read out of this body."""
    return frozenset(
        match["kind"]
        for line in _stripped_lines(body)
        if (match := _TRAILER.fullmatch(line))
    )


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


def _malformed_trailers(lines: Sequence[str]) -> Sequence[str]:
    return tuple(
        f"Malformed {TRAILER_KEY} trailer: {line!r}. Write exactly "
        f"'{TRAILER_KEY}: <{' | '.join(KINDS)}>' at the start of a line, or "
        f"indent the line by four spaces to quote the format without declaring it."
        for line in lines
        if _LOOKALIKE.match(line) and not _TRAILER.fullmatch(line)
    )


def _orphan_highlight_section(lines: Sequence[str]) -> Sequence[str]:
    """A highlight section settles the intent; the flag cannot then be absent."""
    has_section = any(_HIGHLIGHT_HEADING.fullmatch(line) for line in lines)
    has_trailer = any(_TRAILER.fullmatch(line) for line in lines)
    if has_trailer or not has_section:
        return ()
    else:
        return (
            f"This body has a '## Release highlight' section but no {TRAILER_KEY} "
            f"trailer, so the release-time collection would skip it. Add "
            f"'{TRAILER_KEY}: <{' | '.join(KINDS)}>' at the end of the body.",
        )


if __name__ == "__main__":
    sys.exit(main())
