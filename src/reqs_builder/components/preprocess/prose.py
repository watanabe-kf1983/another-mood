"""Prose — convert Markdown files to JSON data model records."""

from collections.abc import Mapping
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

_MD = MarkdownIt()


@dataclass(frozen=True)
class ProseRecord:
    id: str
    title: str | None
    body: str
    mime_type: str

    def to_data(self) -> Mapping[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "body": {
                "mime_type": self.mime_type,
                "content": self.body,
            },
        }


def parse_markdown(content: str, id: str) -> ProseRecord:
    """Parse a Markdown string into a ProseRecord.

    Extracts title from the first H1 heading (None if absent).
    Body is the full file content.
    """
    title = _extract_h1_title(content)
    return ProseRecord(
        id=id,
        title=title,
        body=content,
        mime_type="text/markdown",
    )


def _extract_h1_title(content: str) -> str | None:
    """Extract text from the first H1 heading using Markdown AST."""
    tokens = _MD.parse(content)
    tree = SyntaxTreeNode(tokens)
    for node in tree.walk():
        if node.type == "heading" and node.tag == "h1":
            return node.children[0].content if node.children else None
    return None
