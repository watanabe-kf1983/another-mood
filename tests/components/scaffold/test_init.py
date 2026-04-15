"""Tests for mood init — project scaffolding."""

from pathlib import Path

import pytest

from another_mood.components.scaffold.init import init_project, scaffold_project


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


def test_init_generated_project_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The built-in template should pass `mood build`."""
    from another_mood.config import ProjectConfig
    from another_mood.pipeline.stages import pipeline

    target = tmp_path / "proj"
    init_project(target)

    monkeypatch.chdir(tmp_path)
    config = ProjectConfig(project_dir=Path("proj"))
    config.verify()
    report = pipeline(config).run()
    assert not report.has_errors()
