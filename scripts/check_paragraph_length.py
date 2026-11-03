"""Blocking check on paragraph length across the repository's documents.

Run by ``make ci``. Standard library only, like the other scripts here. Walks
the documents, prints one ``path:line: <length> chars, limit <limit>`` line per
paragraph over the limit of its language, and exits non-zero if there was any.

A paragraph is a run of lines separated by blank lines, with each list item
counted as a paragraph of its own. Headings, tables and fenced code are not
paragraphs and are skipped. The length is the visible text: the URL of a link
(``](...)``) is not read, so it is not counted.
"""

import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOTS = ("README.md", "DEVELOPMENT.md", "docs", "dev-docs/contents")
ENGLISH = ("README.md", "docs")
# English sentences run about 1.9 times the characters of Japanese ones in
# these documents, so the English limit is the Japanese one scaled by that.
LIMITS = {"ja": 200, "en": 380}

_LIST_ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])\s+")
_LINK_TARGET = re.compile(r"\]\([^)]*\)")
_NOT_PARAGRAPH = ("#", "|")
_FENCE = ("```", "~~~")


@dataclass(frozen=True)
class Paragraph:
    line: int
    text: str


def main() -> int:
    overlong = tuple(
        (path, paragraph)
        for path in documents(Path())
        for paragraph in overlong_paragraphs(
            path.read_text(encoding="utf-8"), limit_for(path)
        )
    )
    for path, paragraph in overlong:
        print(
            f"{path}:{paragraph.line}: {visible_length(paragraph.text)} chars, "
            f"limit {limit_for(path)}"
        )

    return 1 if overlong else 0


def documents(root: Path) -> Sequence[Path]:
    """Every Markdown file the rule applies to, as paths relative to root."""
    return tuple(
        path.relative_to(root)
        for start in ROOTS
        for path in _markdown_under(root / start)
    )


def limit_for(path: Path) -> int:
    return LIMITS["en"] if _is_under(path, ENGLISH) else LIMITS["ja"]


def overlong_paragraphs(source: str, limit: int) -> Sequence[Paragraph]:
    return tuple(p for p in paragraphs(source) if visible_length(p.text) > limit)


def visible_length(text: str) -> int:
    return len(_LINK_TARGET.sub("]", text))


def paragraphs(source: str) -> Sequence[Paragraph]:
    """The paragraphs of a Markdown document, wrapped lines joined with a space."""
    return tuple(_paragraphs(source))


def _paragraphs(source: str) -> Iterator[Paragraph]:
    start, texts = 0, list[str]()
    for number, text, opens in _classified_lines(source):
        if opens and texts:
            yield Paragraph(start, " ".join(texts))
            texts = []
        if text is not None:
            start = number if not texts else start
            texts.append(text)
    if texts:
        yield Paragraph(start, " ".join(texts))


def _classified_lines(source: str) -> Iterator[tuple[int, str | None, bool]]:
    """Each line as (number, its prose or None, whether it opens a paragraph).

    A line with no prose still opens: it closes whatever paragraph was open.
    """
    in_fence = False
    for number, raw in enumerate(source.splitlines(), 1):
        text = raw.strip()
        if text.startswith(_FENCE):
            in_fence = not in_fence
            yield number, None, True
        elif in_fence or not text or text.startswith(_NOT_PARAGRAPH):
            yield number, None, True
        elif match := _LIST_ITEM.match(raw):
            yield number, raw[match.end() :].strip(), True
        else:
            yield number, text, False


def _markdown_under(start: Path) -> Sequence[Path]:
    """A root is a file, named as is, or a directory walked for Markdown."""
    return (start,) if start.is_file() else tuple(sorted(start.rglob("*.md")))


def _is_under(path: Path, prefixes: Sequence[str]) -> bool:
    return any(path == Path(p) or path.is_relative_to(p) for p in prefixes)


if __name__ == "__main__":
    sys.exit(main())
