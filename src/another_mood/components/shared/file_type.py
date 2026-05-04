"""FileType — the kinds of source files Another Mood can ingest.

Matching is case-insensitive so that .YAML / .MD / .Yml all work the
same as their lowercase forms.  This mirrors the behavior of common
MIME-type libraries (Python mimetypes, Node mime-types, etc.) and keeps
the user experience consistent across case-sensitive and case-insensitive
filesystems.
"""

from enum import Enum
from pathlib import Path


class FileType(Enum):
    YAML = frozenset({".yaml", ".yml"})
    MARKDOWN = frozenset({".md"})

    def match(self, path: Path) -> bool:
        """True if path is an existing file whose extension matches this file type.

        Extension matching is case-insensitive.  Directories and non-existent
        paths return False even if their names end with a matching suffix.
        """
        return path.is_file() and path.suffix.lower() in self.value
