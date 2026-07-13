"""Reject a user-chosen id that collides with a Windows-reserved name."""

import ntpath
from pathlib import Path

from another_mood.components.shared.user_error import UserError


class WindowsReservedNameError(UserError):
    """A path segment is a Windows-reserved name, user-facing."""

    def __init__(self, segment: str, path: Path) -> None:
        super().__init__(
            f"The path segment {segment!r} in {path} is a reserved filesystem "
            f"name (CON, NUL, COM1…, or a name ending in a dot or space) and "
            f"cannot be written as a file on Windows. Rename the id it comes "
            f"from."
        )


def ensure_not_windows_reserved(path: Path) -> Path:
    """Raise WindowsReservedNameError on the first Windows-reserved segment of
    *path*, else return *path* unchanged so the check can wrap a path in place."""
    reserved = next((part for part in path.parts if ntpath.isreserved(part)), None)
    if reserved is not None:
        raise WindowsReservedNameError(reserved, path)
    return path
