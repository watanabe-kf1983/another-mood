"""Tests for manifest — sbdb.yaml parsing, version gate, and validation."""

from pathlib import Path
from textwrap import dedent

import pytest

from another_mood.components.manifest import (
    Manifest,
    ManifestError,
    UnsupportedSbdbVersionError,
    read_manifest,
)


def _write(project_dir: Path, source: str) -> Path:
    (project_dir / "sbdb.yaml").write_text(source)
    return project_dir


# ── missing / valid ────────────────────────────────────────────────


def test_missing_manifest_is_empty(tmp_path: Path) -> None:
    # No sbdb.yaml: no error, no title (the caller falls back to the dir name).
    assert read_manifest(tmp_path) == Manifest()


def test_reads_title(tmp_path: Path) -> None:
    _write(tmp_path, "sbdb_version: 1\ntitle: My Project\n")
    assert read_manifest(tmp_path) == Manifest(title="My Project")


def test_title_is_optional(tmp_path: Path) -> None:
    _write(tmp_path, "sbdb_version: 1\n")
    assert read_manifest(tmp_path) == Manifest(title=None)


# ── version gate ───────────────────────────────────────────────────


@pytest.mark.parametrize("version", [0, 2, 999, -1])
def test_rejects_unsupported_version(version: int, tmp_path: Path) -> None:
    _write(tmp_path, f"sbdb_version: {version}\ntitle: Other\n")
    with pytest.raises(UnsupportedSbdbVersionError) as exc_info:
        read_manifest(tmp_path)
    assert str(version) in exc_info.value.user_error_message
    assert "sbdb.yaml" in exc_info.value.user_error_message


def test_gate_hint_depends_on_direction(tmp_path: Path) -> None:
    _write(tmp_path, "sbdb_version: 2\n")
    with pytest.raises(UnsupportedSbdbVersionError) as newer:
        read_manifest(tmp_path)
    assert "Upgrade another-mood" in newer.value.user_error_message

    _write(tmp_path, "sbdb_version: 0\n")
    with pytest.raises(UnsupportedSbdbVersionError) as older:
        read_manifest(tmp_path)
    assert "Migrate the project" in older.value.user_error_message


def test_gate_precedes_strict_validation(tmp_path: Path) -> None:
    # A manifest from a future generation may carry keys we do not know.  The
    # gate must fire first, so the user hears "unsupported generation" rather
    # than "unknown key".
    _write(tmp_path, "sbdb_version: 2\nfuture_key: x\n")
    with pytest.raises(UnsupportedSbdbVersionError):
        read_manifest(tmp_path)


@pytest.mark.parametrize("version", ["true", "false", '"1"', "1.5"])
def test_gate_defers_ill_typed_version_to_validation(
    version: str, tmp_path: Path
) -> None:
    # An ill-typed version is a broken manifest, not an unsupported generation.
    # bool is the trap: as an int subclass it reaches the membership test, where
    # `false` would come out as "unsupported generation" instead of a type error.
    _write(tmp_path, f"sbdb_version: {version}\n")
    with pytest.raises(ManifestError):
        read_manifest(tmp_path)


def test_tools_namespace_is_accepted(tmp_path: Path) -> None:
    _write(
        tmp_path,
        dedent(
            """
            sbdb_version: 1
            tools:
              another-mood:
                requires: ">=0.3.5"
            """
        ),
    )
    assert read_manifest(tmp_path) == Manifest()


# ── validation ─────────────────────────────────────────────────────

_INVALID_CASES = [
    pytest.param("title: X\n", id="missing required sbdb_version"),
    pytest.param("sbdb_version: 1\nauthor: me\n", id="unknown top-level key"),
    pytest.param('sbdb_version: "1"\n', id="sbdb_version is a string"),
    pytest.param("sbdb_version: true\n", id="sbdb_version is a bool"),
    pytest.param("sbdb_version: 1.5\n", id="sbdb_version is a float"),
    pytest.param("- a\n- b\n", id="non-mapping root"),
    pytest.param("sbdb_version: [\n", id="malformed yaml"),
]


@pytest.mark.parametrize("source", _INVALID_CASES)
def test_rejects_invalid(source: str, tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        read_manifest(_write(tmp_path, source))


def test_error_carries_file_anchored_diagnostics(tmp_path: Path) -> None:
    # ManifestError anchors diagnostics at sbdb.yaml so the CLI / MCP boundary
    # can point the user at the offending file.
    _write(tmp_path, "sbdb_version: 1\nauthor: me\n")
    with pytest.raises(ManifestError) as exc_info:
        read_manifest(tmp_path)
    assert exc_info.value.diagnostics
    assert "sbdb.yaml" in exc_info.value.user_error_message
