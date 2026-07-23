"""Tests for the scaffold component (blueprints + project copying)."""

from importlib import metadata
from pathlib import Path

import pytest
import yaml

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


class TestScaffoldCopy:
    """Copying the template into the target directory."""

    def test_creates_all_template_files(self, template: Path, tmp_path: Path) -> None:
        target = tmp_path / "proj"

        result = scaffold_project(template, target)

        assert set(result.created) == {
            target / "dir_a" / "file1.txt",
            target / "dir_b" / "file2.txt",
            target / "sbdb.yaml",
        }
        assert (target / "dir_a" / "file1.txt").read_text() == "content1"
        assert (target / "dir_b" / "file2.txt").read_text() == "content2"

    def test_tolerates_unrelated_files(self, template: Path, tmp_path: Path) -> None:
        """A freshly cloned repo (.git, README.md, …) is a valid target."""
        target = tmp_path / "proj"
        (target / ".git").mkdir(parents=True)
        (target / ".git" / "config").write_text("")
        (target / "README.md").write_text("# proj")

        result = scaffold_project(template, target)

        assert (target / "dir_a" / "file1.txt") in result.created
        assert (target / "README.md").read_text() == "# proj"


class TestScaffoldManifest:
    """Generation of the target's fresh sbdb.yaml."""

    def test_titled_after_target_directory(
        self, template: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "proj"

        scaffold_project(template, target)

        assert yaml.safe_load((target / "sbdb.yaml").read_text(encoding="utf-8")) == {
            "sbdb_version": 1,
            "title": "proj",
            "tools": {
                "another-mood": {"minimum_version": metadata.version("another-mood")}
            },
        }

    def test_template_manifest_not_copied(self, template: Path, tmp_path: Path) -> None:
        """The template's own manifest names the template, not the new project."""
        (template / "sbdb.yaml").write_text(
            "sbdb_version: 1\ntitle: Template Title\n", encoding="utf-8"
        )
        target = tmp_path / "proj"

        scaffold_project(template, target)

        manifest = yaml.safe_load((target / "sbdb.yaml").read_text(encoding="utf-8"))
        assert manifest["title"] == "proj"


class TestApplyBlueprint:
    """Applying a bundled blueprint by name."""

    def test_copies_blueprint_with_fresh_manifest(self, tmp_path: Path) -> None:
        target = tmp_path / "proj"

        result = apply_blueprint("starter", target)

        assert (target / "definition" / "schema.yaml").is_file()
        assert (target / "definition" / "schema.yaml") in result.created
        # The bundled blueprint carries its own manifest, but the applied
        # project gets a fresh one titled after the target directory.
        manifest = yaml.safe_load((target / "sbdb.yaml").read_text(encoding="utf-8"))
        assert manifest["title"] == "proj"
        minimum = manifest["tools"]["another-mood"]["minimum_version"]
        assert minimum == metadata.version("another-mood")


class TestBlueprintCatalog:
    """The bundled blueprint manifest (index.yaml)."""

    def test_available_blueprints_lists_starter_and_music(self) -> None:
        blueprints = available_blueprints()

        # Manifest order is preserved; starter must come first.
        names = [b.name for b in blueprints]
        assert names[0] == "starter"
        assert "music" in names
        assert all(b.description for b in blueprints)

    def test_load_blueprints_preserves_manifest_order(self, tmp_path: Path) -> None:
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
