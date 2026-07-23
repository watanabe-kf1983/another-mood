"""Tests for manifest — sbdb.yaml parsing, version gate, and validation."""

from importlib import metadata
from pathlib import Path
from textwrap import dedent

import pytest

from another_mood.components.manifest import (
    Manifest,
    ManifestError,
    MinimumVersionError,
    UnsupportedSbdbVersionError,
    read_manifest,
)

_RUNNING_VERSION = metadata.version("another-mood")


def _write(project_dir: Path, source: str) -> Path:
    (project_dir / "sbdb.yaml").write_text(source)
    return project_dir


def _with_minimum_version(minimum: str) -> str:
    return dedent(
        f"""
        sbdb_version: 1
        tools:
          another-mood:
            minimum_version: {minimum}
        """
    )


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
                minimum_version: "0.0.1"
              other-processor:
                anything: goes
            """
        ),
    )
    assert read_manifest(tmp_path) == Manifest()


# ── minimum_version gate ───────────────────────────────────────────


def test_exactly_running_version_passes(tmp_path: Path) -> None:
    # ">= minimum", not ">": the version that introduced a feature satisfies
    # a project depending on that feature.
    _write(tmp_path, _with_minimum_version(f'"{_RUNNING_VERSION}"'))
    assert read_manifest(tmp_path) == Manifest()


def test_unsatisfied_minimum_version_fails(tmp_path: Path) -> None:
    _write(tmp_path, _with_minimum_version('"999.0"'))
    with pytest.raises(MinimumVersionError) as exc_info:
        read_manifest(tmp_path)
    message = exc_info.value.user_error_message
    assert "999.0" in message
    assert _RUNNING_VERSION in message
    assert "Upgrade another-mood" in message
    assert "sbdb.yaml" in message


def test_minimum_version_gate_precedes_generation_gate(tmp_path: Path) -> None:
    # "Upgrade to X" is more actionable than "unsupported generation", so the
    # minimum_version gate fires first.
    _write(
        tmp_path,
        dedent(
            """
            sbdb_version: 2
            tools:
              another-mood:
                minimum_version: "999.0"
            """
        ),
    )
    with pytest.raises(MinimumVersionError):
        read_manifest(tmp_path)


def test_minimum_version_gate_precedes_strict_validation(tmp_path: Path) -> None:
    # A future-generation manifest may carry keys we do not know; the upgrade
    # hint must not be preempted by "unknown key".
    _write(tmp_path, _with_minimum_version('"999.0"') + "future_key: x\n")
    with pytest.raises(MinimumVersionError):
        read_manifest(tmp_path)


@pytest.mark.parametrize(
    "minimum",
    [
        pytest.param('">=0.3.5"', id="operator"),
        pytest.param('"not-a-version"', id="garbage"),
    ],
)
def test_rejects_non_version_minimum(minimum: str, tmp_path: Path) -> None:
    # Operators and ranges are not part of the field's shape — they fail as
    # "not a valid version", no bespoke rejection rule needed.
    _write(tmp_path, _with_minimum_version(minimum))
    with pytest.raises(ManifestError) as exc_info:
        read_manifest(tmp_path)
    assert "not a valid version" in exc_info.value.user_error_message
    (diagnostic,) = exc_info.value.diagnostics
    assert diagnostic.line == 5  # _with_minimum_version puts the value there


@pytest.mark.parametrize(
    "tools_body",
    [
        pytest.param("  another-mood:\n    minimum_version: 1.0", id="non-string leaf"),
        pytest.param("  another-mood: nonsense", id="non-mapping on the way"),
    ],
)
def test_ill_shaped_minimum_version_defers_to_validation(
    tools_body: str, tmp_path: Path
) -> None:
    # Wherever the shape breaks, the gate steps aside without crashing so
    # strict validation can locate the breakage in the file.
    _write(tmp_path, f"sbdb_version: 1\ntools:\n{tools_body}\n")
    with pytest.raises(ManifestError):
        read_manifest(tmp_path)


def test_rejects_unknown_key_in_mood_namespace(tmp_path: Path) -> None:
    # tools.another-mood is our vocabulary, so unknown keys (e.g. a typo'd
    # minimum_version) must fail loudly.  Other processors' namespaces stay
    # opaque — see test_tools_namespace_is_accepted.
    _write(
        tmp_path,
        'sbdb_version: 1\ntools:\n  another-mood:\n    minimum_versoin: "0.0.1"\n',
    )
    with pytest.raises(ManifestError):
        read_manifest(tmp_path)


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
