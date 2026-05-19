"""Tests for the scaffold component (blueprints + project copying)."""

from pathlib import Path

import pytest

from another_mood.components.scaffold.blueprints import (
    Blueprint,
    apply_blueprint,
    available_blueprints,
    load_blueprints,
    scaffold_project,
)


@pytest.fixture()
def template(tmp_path: Path) -> Path:
    """Create a small synthetic template directory."""
    root = tmp_path / "template"
    (root / "dir_a").mkdir(parents=True)
    (root / "dir_a" / "file1.txt").write_text("content1")
    (root / "dir_b").mkdir(parents=True)
    (root / "dir_b" / "file2.txt").write_text("content2")
    return root


def test_scaffold_creates_all_files(template: Path, tmp_path: Path) -> None:
    target = tmp_path / "proj"

    result = scaffold_project(template, target)

    assert result.all_written is True
    assert set(result.created) == {
        target / "dir_a" / "file1.txt",
        target / "dir_b" / "file2.txt",
    }
    assert list(result.skipped) == []
    assert (target / "dir_a" / "file1.txt").read_text() == "content1"
    assert (target / "dir_b" / "file2.txt").read_text() == "content2"


def test_scaffold_skips_existing_files(template: Path, tmp_path: Path) -> None:
    target = tmp_path / "proj"
    scaffold_project(template, target)

    result = scaffold_project(template, target)

    assert result.all_written is False
    assert list(result.created) == []
    assert set(result.skipped) == {
        target / "dir_a" / "file1.txt",
        target / "dir_b" / "file2.txt",
    }


def test_scaffold_partial_conflict(template: Path, tmp_path: Path) -> None:
    """When some files exist, only those are skipped; others are created."""
    target = tmp_path / "proj"
    conflict = target / "dir_a" / "file1.txt"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("original")

    result = scaffold_project(template, target)

    assert result.all_written is False
    assert list(result.created) == [target / "dir_b" / "file2.txt"]
    assert list(result.skipped) == [conflict]
    assert conflict.read_text() == "original"
    assert (target / "dir_b" / "file2.txt").read_text() == "content2"


def test_apply_blueprint_copies_named_blueprint(tmp_path: Path) -> None:
    target = tmp_path / "proj"

    result = apply_blueprint("starter", target)

    assert result.all_written is True
    assert (target / "definition" / "schema.yaml").is_file()
    assert (target / "definition" / "schema.yaml") in result.created


def test_available_blueprints_lists_starter_and_music() -> None:
    blueprints = available_blueprints()

    # Manifest order is preserved; starter must come first.
    names = [b.name for b in blueprints]
    assert names[0] == "starter"
    assert "music" in names
    assert all(b.description for b in blueprints)


def test_load_blueprints_preserves_manifest_order(tmp_path: Path) -> None:
    (tmp_path / "index.yaml").write_text(
        "blueprints:\n"
        "  - name: gamma\n    description: g.\n"
        "  - name: alpha\n    description: a.\n"
        "  - name: beta\n    description: b.\n",
        encoding="utf-8",
    )

    blueprints = load_blueprints(tmp_path)

    assert list(blueprints) == [
        Blueprint(name="gamma", description="g."),
        Blueprint(name="alpha", description="a."),
        Blueprint(name="beta", description="b."),
    ]
