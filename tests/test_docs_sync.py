"""Sync check — built-in schema YAMLs vs their mirrored copies under docs/.

The reference docs under ``docs/reference/`` link to mirrored copies of
the built-in schema files at ``docs/reference/schemas/*.yaml``.  The
canonical source lives at ``src/another_mood/resources/schemas/``; the
mirror is a one-way build artifact, regenerated with ``make
mirror-schemas``.  This test fails when the two diverge so that a
contributor who edits the source (or adds / removes a schema) without
re-syncing is caught at CI time.
"""

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SOURCE_DIR = _REPO_ROOT / "src" / "another_mood" / "resources" / "schemas"
_MIRROR_DIR = _REPO_ROOT / "docs" / "reference" / "schemas"

_RESYNC_HINT = "Run `make mirror-schemas` to regenerate the mirror."


def test_mirror_matches_source() -> None:
    source = {p.name: p.read_text(encoding="utf-8") for p in _SOURCE_DIR.glob("*.yaml")}
    mirror = {p.name: p.read_text(encoding="utf-8") for p in _MIRROR_DIR.glob("*.yaml")}

    missing = sorted(source.keys() - mirror.keys())
    extra = sorted(mirror.keys() - source.keys())
    if missing or extra:
        pytest.fail(
            f"schema file set differs between {_SOURCE_DIR} and {_MIRROR_DIR}: "
            f"missing in mirror={missing}, extra in mirror={extra}. {_RESYNC_HINT}"
        )

    drifted = sorted(name for name in source if mirror[name] != source[name])
    if drifted:
        pytest.fail(
            f"docs/reference/schemas/{{{','.join(drifted)}}} drifted from "
            f"src/another_mood/resources/schemas/. {_RESYNC_HINT}"
        )
