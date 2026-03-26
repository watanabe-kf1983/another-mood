"""Tests for SectionProcessorImpl — renders template and writes page to disk."""

from pathlib import Path

from jinja2 import DictLoader, Environment

from reqs_builder.components.generator.section_processor import SectionProcessorImpl


def _make_env(templates: dict[str, str]) -> Environment:
    env = Environment(keep_trailing_newline=True)
    env.loader = DictLoader(templates)
    return env


class TestSectionProcessorImpl:
    def test_writes_file_to_correct_path(self, tmp_path: Path) -> None:
        env = _make_env({"profile.md": "hi {{ id }}"})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        processor("profile", {"id": "alice", "name": "Alice"})

        assert (tmp_path / "profile" / "alice.md").exists()

    def test_file_contains_rendered_content(self, tmp_path: Path) -> None:
        env = _make_env({"profile.md": "hi {{ id }}"})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        processor("profile", {"id": "alice", "name": "Alice"})

        assert (tmp_path / "profile" / "alice.md").read_text() == "hi alice"

    def test_returns_empty_string(self, tmp_path: Path) -> None:
        env = _make_env({"profile.md": "content"})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        result = processor("profile", {"id": "alice"})

        assert result == ""

    def test_creates_subdirectory(self, tmp_path: Path) -> None:
        env = _make_env({"entity-detail.md": ""})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        processor("entity-detail", {"id": "user"})

        assert (tmp_path / "entity-detail").is_dir()

    def test_multiple_pages_in_same_directory(self, tmp_path: Path) -> None:
        env = _make_env({"detail.md": "{{ id }}"})
        processor = SectionProcessorImpl(env=env, out_dir=tmp_path)
        processor("detail", {"id": "a"})
        processor("detail", {"id": "b"})

        assert (tmp_path / "detail" / "a.md").read_text() == "a"
        assert (tmp_path / "detail" / "b.md").read_text() == "b"
