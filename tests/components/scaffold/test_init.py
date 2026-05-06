"""Tests for mood init — project scaffolding."""

from pathlib import Path

import pytest

from another_mood.components.scaffold.init import (
    UnknownTemplateError,
    available_templates,
    init_project,
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

    assert result is True
    assert (target / "dir_a" / "file1.txt").read_text() == "content1"
    assert (target / "dir_b" / "file2.txt").read_text() == "content2"


def test_scaffold_skips_existing_files(template: Path, tmp_path: Path) -> None:
    target = tmp_path / "proj"
    scaffold_project(template, target)

    result = scaffold_project(template, target)

    assert result is False


def test_scaffold_partial_conflict(template: Path, tmp_path: Path) -> None:
    """When some files exist, only those are skipped; others are created."""
    target = tmp_path / "proj"
    conflict = target / "dir_a" / "file1.txt"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("original")

    result = scaffold_project(template, target)

    assert result is False
    assert conflict.read_text() == "original"
    assert (target / "dir_b" / "file2.txt").read_text() == "content2"


def test_available_templates_lists_starter_and_examples() -> None:
    templates = available_templates()

    # starter is always present; examples/* are exposed under their dir name.
    assert "starter" in templates
    assert "ecommerce" in templates
    assert templates["starter"].is_dir()
    assert templates["ecommerce"].is_dir()


def test_init_project_default_uses_starter(tmp_path: Path) -> None:
    target = tmp_path / "proj"

    result = init_project(target)

    assert result is True
    # starter ships a definition/schema.yaml.
    assert (target / "definition" / "schema.yaml").is_file()


def test_init_project_with_named_template(tmp_path: Path) -> None:
    target = tmp_path / "proj"

    result = init_project(target, template="ecommerce")

    assert result is True
    assert (target / "definition" / "schema.yaml").is_file()


def test_init_project_unknown_template_raises(tmp_path: Path) -> None:
    target = tmp_path / "proj"

    with pytest.raises(UnknownTemplateError) as excinfo:
        init_project(target, template="does-not-exist")

    assert excinfo.value.name == "does-not-exist"
    assert "starter" in excinfo.value.available
    assert not target.exists()
