"""Reject a user-chosen id that collides with a Windows-reserved name."""

from pathlib import Path

from another_mood.components.shared.user_error import UserError

# Vendored from CPython's `ntpath._isreservedname` tables. The public
# `ntpath.isreserved` exists only on 3.13+, and this copy is what lets the
# supported Python floor stay at 3.12. Re-check against upstream ntpath when
# raising the floor to 3.13.
_RESERVED_CHARS = frozenset(
    {chr(i) for i in range(32)} | {'"', "*", ":", "<", ">", "?", "|", "/", "\\"}
)

_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{c}" for c in "123456789\xb9\xb2\xb3"}
    | {f"LPT{c}" for c in "123456789\xb9\xb2\xb3"}
)


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
    # The anchor ("/", "C:\\") holds separators and a colon, which the segment
    # predicate reads as reserved. It is not a user-chosen id, so drop it.
    segments = path.parts[1:] if path.anchor else path.parts
    reserved = next((s for s in segments if _is_reserved_segment(s)), None)
    if reserved is not None:
        raise WindowsReservedNameError(reserved, path)
    return path


def _is_reserved_segment(segment: str) -> bool:
    # Refer to "Naming Files, Paths, and Namespaces":
    # https://docs.microsoft.com/en-us/windows/win32/fileio/naming-a-file
    # Trailing dots and spaces are reserved.
    if segment[-1:] in (".", " "):
        return segment not in (".", "..")
    # Wildcards, separators, colon, and pipe (*?"<>/\:|) are reserved, as are
    # the ASCII control characters. Colon is reserved for file streams.
    if _RESERVED_CHARS.intersection(segment):
        return True
    # DOS device names are reserved (e.g. "nul" or "nul .txt"). The rules are
    # complex and vary across Windows versions, so on the side of caution this
    # reports True for names that may not be reserved.
    return segment.partition(".")[0].rstrip(" ").upper() in _RESERVED_NAMES
