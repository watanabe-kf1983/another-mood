"""Tests for manifest — sbdb.yaml parsing and ManifestSchema validation.

Scope is V1: parse + strict validation + title extraction. The sbdb_version
value gate (membership in the supported set) is a separate task, so any integer
sbdb_version is accepted here.
"""

from pathlib import Path
from textwrap import dedent

import pytest

from another_mood.components.manifest import Manifest, ManifestError, read_manifest


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


def test_value_gate_is_deferred(tmp_path: Path) -> None:
    # V1 checks sbdb_version is an integer but not its value; any integer is
    # accepted (the membership gate is a separate task).
    _write(tmp_path, "sbdb_version: 999\ntitle: Future\n")
    assert read_manifest(tmp_path) == Manifest(title="Future")


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
