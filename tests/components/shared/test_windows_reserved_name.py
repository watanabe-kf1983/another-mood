"""Tests for the reserved-name check.

Windows' silent reserved-name / trailing-dot behavior cannot be reproduced
on POSIX, so these exercise the pure predicate directly rather than through
an actual file write.
"""

from pathlib import Path

import pytest

from another_mood.components.shared.windows_reserved_name import (
    WindowsReservedNameError,
    ensure_not_windows_reserved,
)


class TestEnsureNotWindowsReserved:
    @pytest.mark.parametrize(
        "path",
        [
            "CON",
            "con",
            "CON.md",
            "com1.txt",
            "NUL",
            "lpt9",
            "trailing.",
            "trailing ",
            "colon:name",  # reserved on Windows as a file-stream separator
            "pipe|name",
            "wild*card",
            "ctrl\x01char",
        ],
    )
    def test_raises_on_reserved_segment(self, path: str) -> None:
        with pytest.raises(WindowsReservedNameError):
            ensure_not_windows_reserved(Path(path))

    def test_raises_on_reserved_segment_anywhere_in_path(self) -> None:
        # The offending segment need not be the leaf.
        with pytest.raises(WindowsReservedNameError):
            ensure_not_windows_reserved(Path("erds/CON/entities/user.md"))

    def test_raises_on_reserved_segment_under_an_absolute_path(self) -> None:
        with pytest.raises(WindowsReservedNameError):
            ensure_not_windows_reserved(Path("/tmp/out/CON.md"))

    def test_error_names_the_offending_segment(self) -> None:
        with pytest.raises(WindowsReservedNameError) as excinfo:
            ensure_not_windows_reserved(Path("dir/COM1.yaml"))
        assert "'COM1.yaml'" in excinfo.value.user_error_message

    @pytest.mark.parametrize(
        "path",
        [
            "normal.md",
            "CONtext.md",  # reserved name is a prefix, not the whole segment
            "erds/user-management/entities/user.md",
            "書籍/モーニング娘。.md",  # non-ASCII ids stay clear
            "com0.txt",  # COM0 is not reserved (COM1..COM9 are)
            # The anchor of an absolute path carries separators (and a colon on
            # Windows), but is not a user-chosen id and must not be rejected.
            "/tmp/out/user.md",
        ],
    )
    def test_passes_clean_paths(self, path: str) -> None:
        # A clean path does not raise and is returned unchanged, so the check
        # can wrap a path expression in place.
        assert ensure_not_windows_reserved(Path(path)) == Path(path)
