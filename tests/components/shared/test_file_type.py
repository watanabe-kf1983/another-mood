"""Tests for FileType."""

from pathlib import Path

import pytest

from another_mood.components.shared.file_type import FileType


# ── Class behavior ─────────────────────────────────────────────────
# How FileType.match works, regardless of which types exist.
# Adding a new FileType does not require updating these tests.


@pytest.mark.parametrize(
    "name,expected",
    [
        # Case-insensitive matching
        ("data.yaml", True),
        ("OTHER.YAML", True),
        ("Mixed.Yaml", True),
        ("weird.YmL", True),
        # Unsupported extensions
        ("data.json", False),
        ("README", False),
        ("data.yamll", False),
        # Dot-prefix is part of the stem; the extension alone decides
        (".hidden.yaml", True),
    ],
)
def test_match_against_yaml_file(tmp_path: Path, name: str, expected: bool) -> None:
    f = tmp_path / name
    f.touch()
    assert FileType.YAML.match(f) is expected


def test_match_rejects_directory(tmp_path: Path) -> None:
    d = tmp_path / "weird.yaml"
    d.mkdir()
    assert not FileType.YAML.match(d)


def test_match_rejects_nonexistent_path(tmp_path: Path) -> None:
    assert not FileType.YAML.match(tmp_path / "missing.yaml")


# ── Extension registration ─────────────────────────────────────────
# Which extensions are recognized as which type.
# When adding a new FileType, add rows here.


@pytest.mark.parametrize(
    "name,file_type",
    [
        ("data.yaml", FileType.YAML),
        ("data.yml", FileType.YAML),
        ("notes.md", FileType.MARKDOWN),
    ],
)
def test_extension_is_registered(
    tmp_path: Path, name: str, file_type: FileType
) -> None:
    f = tmp_path / name
    f.touch()
    assert file_type.match(f)
