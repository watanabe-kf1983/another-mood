"""Tests for source-layout resolution and its existence verification."""

from pathlib import Path

import pytest

from another_mood.components.shared.user_error import UserError
from another_mood.layout import SourceLayoutError, resolve_layout


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
            "schema_file",
            "reports_file",
            "contents_dir",
            "queries_dir",
            "templates_dir",
        )
        assert all(name in message for name in names)

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

    def test_is_a_user_error(self) -> None:
        assert issubclass(SourceLayoutError, UserError)
