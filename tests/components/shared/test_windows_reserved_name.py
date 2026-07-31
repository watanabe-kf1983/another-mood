"""Tests for the reserved-name check.

Windows' silent reserved-name / trailing-dot behavior cannot be reproduced
on POSIX, so these exercise the pure predicate directly rather than through
an actual file write.
"""

import itertools
import ntpath
import sys
from pathlib import Path

import pytest

from another_mood.components.shared.windows_reserved_name import (
    WindowsReservedNameError,
    _is_reserved_segment,  # pyright: ignore[reportPrivateUsage]
    ensure_not_windows_reserved,
)

# Characters and fragments that exercise every branch of the predicate:
# ordinary, control, the reserved punctuation, and device-name material.
_INTERESTING = 'aC0.$ :|*<>?"\\/\x01\xb9nulcom1LPT9'

# Names too long for the generated corpus below, covering the device-name
# rules that a segment-level predicate is most likely to get wrong.
_INTERESTING_NAMES = (
    "CON",
    "CONIN$",
    "CONOUT$",
    "conin$",
    "nul .txt",
    "con .md",
    "COM1 .yaml",
    "nul.txt",
    "com0.txt",
    "CONtext.md",
    "書籍",
    "モーニング娘。.md",
    ".",
    "..",
    "...",
)


def _corpus() -> list[str]:
    generated = (
        "".join(t) for n in (1, 2, 3) for t in itertools.product(_INTERESTING, repeat=n)
    )
    return [*generated, *_INTERESTING_NAMES]


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


@pytest.mark.skipif(
    sys.version_info < (3, 13),
    reason="the reference implementation, ntpath.isreserved, is 3.13+",
)
class TestMatchesStdlibReference:
    """Pin the vendored predicate to `ntpath.isreserved`, which it replaces.

    The vendored copy is what lets the supported floor stay at 3.12, so it
    cannot be checked on the floor itself -- these run on the CI matrix job
    for the newest supported version, where the stdlib reference exists.
    """

    def test_is_never_looser_than_the_stdlib(self) -> None:
        # The safety-critical direction: a name the stdlib calls reserved must
        # never slip through, or an id that silently fails on Windows ships.
        missed: list[str] = []
        if sys.version_info >= (3, 13):
            missed = [
                s
                for s in _corpus()
                if ntpath.isreserved(s) and not _is_reserved_segment(s)
            ]
        assert missed == []

    def test_agrees_exactly_on_segment_shaped_input(self) -> None:
        # The two diverge only on input holding a separator or a drive colon,
        # which `ntpath.isreserved` strips as a root but a `Path.parts`
        # segment never carries -- the anchor is dropped before it gets here.
        disagreed: list[str] = []
        if sys.version_info >= (3, 13):
            disagreed = [
                s
                for s in _corpus()
                if not any(c in s for c in "/\\:")
                and _is_reserved_segment(s) != ntpath.isreserved(s)
            ]
        assert disagreed == []
