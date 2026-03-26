"""Prose — convert Markdown files to JSON data model records."""

import re
from typing import Any

_H1_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def parse_markdown(content: str, id: str) -> dict[str, Any]:
    """Parse a Markdown string into a prose record.

    Returns a dict with id, title (from first H1 or None), and body
    as a Typed Value with _mime_type and _content.
    """
    match = _H1_PATTERN.search(content)
    return {
        "id": id,
        "title": match.group(1).strip() if match else None,
        "body": {
            "_mime_type": "text/markdown",
            "_content": content,
        },
    }
