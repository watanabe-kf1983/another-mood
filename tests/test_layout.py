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
    """Create the minimal source layout ``resolve_layout`` requires."""
    definition = project_dir / "definition"
    (definition / "queries").mkdir(parents=True)
    (definition / "templates").mkdir(parents=True)
    (project_dir / "contents").mkdir(parents=True)
    (definition / "schema.yaml").write_text("")
    (definition / "reports.yaml").write_text("")


class TestResolveLayout:
    def test_derives_v1_paths_from_project_dir(self, tmp_path: Path) -> None:
        scaffold_sources(tmp_path)
        layout = resolve_layout(tmp_path)
        assert layout.definition_dir == tmp_path / "definition"
        assert layout.schema_file == tmp_path / "definition" / "schema.yaml"
        assert layout.reports_file == tmp_path / "definition" / "reports.yaml"
        assert layout.contents_dir == tmp_path / "contents"
        assert layout.queries_dir == tmp_path / "definition" / "queries"
        assert layout.templates_dir == tmp_path / "definition" / "templates"

    def test_lists_every_missing_path(self, tmp_path: Path) -> None:
        with pytest.raises(SourceLayoutError) as exc_info:
            resolve_layout(tmp_path / "missing")
        message = exc_info.value.user_error_message
        assert "Source paths not found:" in message
        names = (
            "definition_dir",
            "schema_file",
            "reports_file",
            "contents_dir",
            "queries_dir",
            "templates_dir",
        )
        assert all(name in message for name in names)

    def test_tolerates_a_missing_manifest(self, tmp_path: Path) -> None:
        """The manifest is optional while "absent means sbdb_version 1" holds."""
        scaffold_sources(tmp_path)

        layout = resolve_layout(tmp_path)

        assert layout.manifest_file == tmp_path / "sbdb.yaml"
        assert not layout.manifest_file.exists()

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
        (tmp_path / "definition" / "queries" / "notes.txt").write_text("")
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
        """Optional for ``verify``, occupied for ``verify_absent``."""
        (tmp_path / "sbdb.yaml").write_text("sbdb_version: 1\n")

        with pytest.raises(ProjectExistsError, match="sbdb.yaml"):
            verify_absent(tmp_path)


class TestSourceLayoutError:
    def test_is_a_user_error(self) -> None:
        assert issubclass(SourceLayoutError, UserError)

    def test_project_exists_error_is_a_user_error(self) -> None:
        assert issubclass(ProjectExistsError, UserError)
