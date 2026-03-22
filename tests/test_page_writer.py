"""Tests for PageWriter — SectionProcessor implementation.

Tested independently of Jinja2 by injecting a mock render function.
"""

from pathlib import Path
from typing import Any

from reqs_builder.generator.page_writer import PageWriter


def _mock_render(template_name: str, data: dict[str, Any]) -> str:
    return f"rendered:{template_name}:{data['id']}"


class TestPageWriter:
    def test_writes_file_to_correct_path(self, tmp_path: Path) -> None:
        writer = PageWriter(out_dir=tmp_path, render=_mock_render)
        writer("profile", {"id": "alice", "name": "Alice"})

        assert (tmp_path / "profile" / "alice.md").exists()

    def test_file_contains_rendered_content(self, tmp_path: Path) -> None:
        writer = PageWriter(out_dir=tmp_path, render=_mock_render)
        writer("profile", {"id": "alice", "name": "Alice"})

        assert (
            tmp_path / "profile" / "alice.md"
        ).read_text() == "rendered:profile:alice"

    def test_returns_empty_string(self, tmp_path: Path) -> None:
        writer = PageWriter(out_dir=tmp_path, render=_mock_render)
        result = writer("profile", {"id": "alice"})

        assert result == ""

    def test_creates_subdirectory(self, tmp_path: Path) -> None:
        writer = PageWriter(out_dir=tmp_path, render=_mock_render)
        writer("entity-detail", {"id": "user"})

        assert (tmp_path / "entity-detail").is_dir()

    def test_multiple_pages_in_same_directory(self, tmp_path: Path) -> None:
        writer = PageWriter(out_dir=tmp_path, render=_mock_render)
        writer("detail", {"id": "a"})
        writer("detail", {"id": "b"})

        assert (tmp_path / "detail" / "a.md").read_text() == "rendered:detail:a"
        assert (tmp_path / "detail" / "b.md").read_text() == "rendered:detail:b"

    def test_passes_template_name_and_data_to_render(self, tmp_path: Path) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        def recording_render(template_name: str, data: dict[str, Any]) -> str:
            calls.append((template_name, data))
            return ""

        writer = PageWriter(out_dir=tmp_path, render=recording_render)
        writer("card", {"id": "x", "title": "Hello"})

        assert calls == [("card", {"id": "x", "title": "Hello"})]
