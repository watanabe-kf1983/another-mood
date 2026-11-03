"""Tests for source-layout resolution and its existence verification."""

from pathlib import Path

import pytest

from another_mood.components.shared.user_error import UserError
from another_mood.layout import (
    ProjectExistsError,
    SourceLayoutError,
    resolve_layout,
    verify_absent,
)


def scaffold_sources(project_dir: Path) -> None:
    """Create the full source layout ``resolve_layout`` reads."""
    definition = project_dir / "definition"
    (definition / "views").mkdir(parents=True)
    (definition / "templates").mkdir(parents=True)
    (project_dir / "contents").mkdir(parents=True)
    (definition / "schema.yaml").write_text("")
    (definition / "reports.yaml").write_text("")
    (project_dir / "sbdb.yaml").write_text("sbdb_version: 1\n")


class TestResolveLayout:
    def test_derives_v1_paths_from_project_dir(self, tmp_path: Path) -> None:
        scaffold_sources(tmp_path)
        layout = resolve_layout(tmp_path)
        assert layout.definition_dir == tmp_path / "definition"
        assert layout.schema_file == tmp_path / "definition" / "schema.yaml"
        assert layout.reports_file == tmp_path / "definition" / "reports.yaml"
        assert layout.contents_dir == tmp_path / "contents"
        assert layout.views_dir == tmp_path / "definition" / "views"
        assert layout.templates_dir == tmp_path / "definition" / "templates"

    def test_lists_every_missing_required_path(self, tmp_path: Path) -> None:
        with pytest.raises(SourceLayoutError) as exc_info:
            resolve_layout(tmp_path / "missing")
        message = exc_info.value.user_error_message
        assert "Source paths not found:" in message
        names = (
            "manifest_file",
            "definition_dir",
            "schema_file",
            "reports_file",
            "templates_dir",
        )
        assert all(name in message for name in names)
        assert "contents_dir" not in message
        assert "views_dir" not in message

    def test_allows_absent_contents_and_views(self, tmp_path: Path) -> None:
        """Git keeps no empty directory, so a fresh clone may lack both."""
        scaffold_sources(tmp_path)
        (tmp_path / "contents").rmdir()
        (tmp_path / "definition" / "views").rmdir()
        resolve_layout(tmp_path)

    def test_rejects_file_where_optional_dir_expected(self, tmp_path: Path) -> None:
        scaffold_sources(tmp_path)
        (tmp_path / "contents").rmdir()
        (tmp_path / "contents").write_text("")
        with pytest.raises(SourceLayoutError, match="contents_dir"):
            resolve_layout(tmp_path)

    def test_requires_the_manifest(self, tmp_path: Path) -> None:
        """The backstop: in a build ``read_manifest`` gets there first."""
        scaffold_sources(tmp_path)
        (tmp_path / "sbdb.yaml").unlink()

        with pytest.raises(SourceLayoutError, match="manifest_file"):
            resolve_layout(tmp_path)

    def test_reports_only_missing_paths(self, tmp_path: Path) -> None:
        scaffold_sources(tmp_path)
        (tmp_path / "definition" / "schema.yaml").unlink()
        with pytest.raises(SourceLayoutError, match="schema_file") as exc_info:
            resolve_layout(tmp_path)
        assert "contents_dir" not in str(exc_info.value)

    def test_rejects_dir_where_file_expected(self, tmp_path: Path) -> None:
        scaffold_sources(tmp_path)
        (tmp_path / "definition" / "schema.yaml").unlink()
        (tmp_path / "definition" / "schema.yaml").mkdir()
        with pytest.raises(SourceLayoutError, match="schema_file"):
            resolve_layout(tmp_path)


class TestUnknownDefinitionEntries:
    """Keeps: design/Manifest › 知らない入力は、黙って読み飛ばさずエラーにする"""

    def test_rejects_unknown_file(self, tmp_path: Path) -> None:
        scaffold_sources(tmp_path)
        (tmp_path / "definition" / "notes.yaml").write_text("")
        with pytest.raises(SourceLayoutError) as exc_info:
            resolve_layout(tmp_path)
        message = exc_info.value.user_error_message
        assert "Unknown entries under definition/:" in message
        assert "notes.yaml" in message
        assert "schema.yaml" in message  # the known set, as a hint

    def test_rejects_unknown_directory(self, tmp_path: Path) -> None:
        scaffold_sources(tmp_path)
        (tmp_path / "definition" / "quries").mkdir()
        with pytest.raises(SourceLayoutError, match="quries"):
            resolve_layout(tmp_path)

    def test_allows_hidden_entries(self, tmp_path: Path) -> None:
        scaffold_sources(tmp_path)
        (tmp_path / "definition" / ".gitignore").write_text("")
        (tmp_path / "definition" / ".cache").mkdir()
        resolve_layout(tmp_path)

    def test_allows_unknown_entries_below_top_level(self, tmp_path: Path) -> None:
        scaffold_sources(tmp_path)
        (tmp_path / "definition" / "templates" / "partials").mkdir()
        (tmp_path / "definition" / "views" / "notes.txt").write_text("")
        resolve_layout(tmp_path)

    def test_allows_unknown_entries_beside_definition(self, tmp_path: Path) -> None:
        scaffold_sources(tmp_path)
        (tmp_path / "README.md").write_text("")
        (tmp_path / ".git").mkdir()
        resolve_layout(tmp_path)


class TestVerifyAbsent:
    """The scaffold-side guard: every path mood writes must be free."""

    def test_accepts_an_empty_or_missing_directory(self, tmp_path: Path) -> None:
        verify_absent(tmp_path / "missing")
        verify_absent(tmp_path)

    def test_accepts_unrelated_entries(self, tmp_path: Path) -> None:
        """A freshly cloned repo (.git, README.md, …) is a valid target."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "README.md").write_text("")

        verify_absent(tmp_path)

    def test_rejects_a_lone_contents_dir(self, tmp_path: Path) -> None:
        """A half-populated project is rejected: no merging into one."""
        (tmp_path / "contents").mkdir()

        with pytest.raises(ProjectExistsError) as exc_info:
            verify_absent(tmp_path)

        assert list(exc_info.value.existing) == [tmp_path / "contents"]

    def test_rejects_a_lone_manifest(self, tmp_path: Path) -> None:
        (tmp_path / "sbdb.yaml").write_text("sbdb_version: 1\n")

        with pytest.raises(ProjectExistsError, match="sbdb.yaml"):
            verify_absent(tmp_path)


class TestSourceLayoutError:
    def test_is_a_user_error(self) -> None:
        assert issubclass(SourceLayoutError, UserError)

    def test_project_exists_error_is_a_user_error(self) -> None:
        assert issubclass(ProjectExistsError, UserError)
