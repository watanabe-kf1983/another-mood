"""Tests for mood_view_processor — MoodViewExtension and MoodViewProcessorImpl."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from jinja2 import Environment, TemplateSyntaxError

from another_mood.components.generator.data_tree import wrap_tree
from another_mood.components.generator.mood_view_processor import (
    PROCESSOR_KEY,
    MoodViewExtension,
    MoodViewProcessorImpl,
)
from another_mood.components.generator.output_formats.md import MD
from another_mood.components.generator.edition import PagingPolicy
from another_mood.components.generator.template_engine import TemplateEngine
from another_mood.components.shared.user_source.diagnostic import FileValidationError


# -- Helpers --


@dataclass
class MockProcessor:
    """Records calls and returns a fixed string."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=lambda: [])
    return_value: str = ""

    def __call__(self, template_name: str, data: dict[str, Any]) -> str:
        self.calls.append((template_name, data))
        return self.return_value


def _make_extension_env(processor: MockProcessor) -> Environment:
    env = Environment(extensions=[MoodViewExtension], keep_trailing_newline=True)
    env.globals[PROCESSOR_KEY] = processor  # type: ignore[assignment]
    return env


# -- MoodViewExtension --


class TestMoodViewParsing:
    """Extension correctly parses template name and data from the tag."""

    def test_receives_template_name_and_data(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% mood_view "profile.md" with user %}')
        template.render(user={"id": "alice", "name": "Alice"})

        assert len(mock.calls) == 1
        assert mock.calls[0][0] == "profile.md"
        assert mock.calls[0][1] == {"id": "alice", "name": "Alice"}

    def test_data_is_resolved_expression(self) -> None:
        """The with-expression is evaluated, not passed as a string."""
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string('{% mood_view "card.md" with items[0] %}')
        template.render(items=[{"id": "x", "val": 42}])

        assert mock.calls[0][1] == {"id": "x", "val": 42}

    def test_called_once_per_tag(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string(
            '{% mood_view "a.md" with x %}{% mood_view "b.md" with y %}'
        )
        template.render(x={"id": "1"}, y={"id": "2"})

        assert len(mock.calls) == 2
        assert mock.calls[0][0] == "a.md"
        assert mock.calls[1][0] == "b.md"

    def test_inside_for_loop(self) -> None:
        mock = MockProcessor()
        env = _make_extension_env(mock)
        template = env.from_string(
            '{% for item in items %}{% mood_view "detail.md" with item %}{% endfor %}'
        )
        template.render(items=[{"id": "a"}, {"id": "b"}, {"id": "c"}])

        assert len(mock.calls) == 3
        assert [c[1]["id"] for c in mock.calls] == ["a", "b", "c"]


class TestMoodViewOutput:
    """Extension returns renderer's output into the Jinja2 result."""

    def test_return_value_appears_in_output(self) -> None:
        mock = MockProcessor(return_value="REPLACED")
        env = _make_extension_env(mock)
        template = env.from_string('before{% mood_view "x.md" with d %}after')
        result = template.render(d={"id": "1"})

        assert result == "beforeREPLACEDafter"

    def test_empty_return_produces_nothing(self) -> None:
        mock = MockProcessor(return_value="")
        env = _make_extension_env(mock)
        template = env.from_string('before{% mood_view "x.md" with d %}after')
        result = template.render(d={"id": "1"})

        assert result == "beforeafter"


class TestMoodViewSyntaxError:
    def test_missing_with_keyword(self) -> None:
        env = _make_extension_env(MockProcessor())
        with pytest.raises(TemplateSyntaxError, match="expected token 'with'"):
            env.from_string('{% mood_view "profile.md" user %}')


class TestMoodViewSubtreeGuard:
    """A node subject must lie within the host ``this``'s subtree; otherwise
    the tag raises a build error pointing at its own source line (B12)."""

    _TREE = {
        "albums": [{"id": "a1", "title": "A1"}],
        "prose": [{"id": "p1", "body": "note"}],
    }

    def _render(
        self, template: str, this: object, subject: object
    ) -> tuple[MockProcessor, str]:
        mock = MockProcessor(return_value="OK")
        env = _make_extension_env(mock)
        result = env.from_string(template).render(this=this, subject=subject)
        return mock, result

    def test_descendant_subject_passes(self) -> None:
        tree = wrap_tree(self._TREE)
        mock, result = self._render(
            '{% mood_view "x.md" with subject %}', this=tree, subject=tree["albums"][0]
        )
        assert result == "OK"
        assert mock.calls == [("x.md", tree["albums"][0])]

    def test_subject_equal_to_host_passes(self) -> None:
        tree = wrap_tree(self._TREE)
        album = tree["albums"][0]
        _, result = self._render(
            '{% mood_view "x.md" with subject %}', this=album, subject=album
        )
        assert result == "OK"

    def test_non_descendant_subject_raises_at_tag_line(self) -> None:
        tree = wrap_tree(self._TREE)
        with pytest.raises(FileValidationError) as exc:
            self._render(
                '\n\n{% mood_view "x.md" with subject %}',
                this=tree["albums"][0],
                subject=tree["prose"][0],
            )
        (diag,) = exc.value.diagnostics
        assert diag.line == 3
        assert diag.source == "mood_view"
        # The error names both the off-subtree subject and the host.
        assert "/prose/p1" in diag.message
        assert "/albums/a1" in diag.message

    def test_sibling_whose_name_prefixes_host_is_rejected(self) -> None:
        # `/album_tracklist/x` is a sibling of `/album`, not a descendant, even
        # though its anchor path string-prefixes the host's -- ancestry is by
        # identity, so a prefix shortcut would wrongly accept it.
        tree = wrap_tree({"album": {"id": "a"}, "album_tracklist": [{"id": "x"}]})
        with pytest.raises(FileValidationError):
            self._render(
                '{% mood_view "x.md" with subject %}',
                this=tree["album"],
                subject=tree["album_tracklist"][0],
            )

    def test_non_node_subject_is_exempt(self) -> None:
        # A string carries no anchor and no page identity, so it is exempt even
        # under a node host.
        tree = wrap_tree(self._TREE)
        mock, result = self._render(
            '{% mood_view "x.md" with subject %}',
            this=tree["albums"][0],
            subject="just a string",
        )
        assert result == "OK"
        assert mock.calls == [("x.md", "just a string")]

    def test_node_subject_under_non_node_host_raises(self) -> None:
        # A real node cannot be a descendant of a non-node host.
        tree = wrap_tree(self._TREE)
        with pytest.raises(FileValidationError):
            self._render(
                '{% mood_view "x.md" with subject %}',
                this="not a node",
                subject=tree["albums"][0],
            )


# -- MoodViewProcessorImpl --


@dataclass
class _MockEngine:
    """Captures calls to render / render_to_file for routing assertions."""

    rendered: list[tuple[str, dict[str, Any]]] = field(default_factory=lambda: [])
    written: list[tuple[str, dict[str, Any], Path]] = field(default_factory=lambda: [])
    render_return: str = "INLINED"

    def render(self, template_name: str, data: dict[str, Any]) -> str:
        self.rendered.append((template_name, data))
        return self.render_return

    def render_to_file(
        self, template_name: str, data: dict[str, Any], out_path: Path
    ) -> None:
        self.written.append((template_name, data, out_path))


class TestMoodViewProcessorImplFilePerRouting:
    """A real node's split-vs-inline decision follows ``file_per`` (C4)."""

    _TREE = {"members": [{"id": "alice", "name": "Alice"}]}

    def _member(self) -> object:
        return wrap_tree(self._TREE)["members"][0]

    def test_node_in_file_per_splits(self) -> None:
        engine = _MockEngine()
        paging = PagingPolicy(("members.item",))
        processor = MoodViewProcessorImpl(engine=engine, paging=paging)  # type: ignore[arg-type]
        member = self._member()
        result = processor("member.md", member)

        assert engine.written == [("member.md", member, Path("members/alice.md"))]
        assert engine.rendered == []
        assert result == ""

    def test_node_absent_from_file_per_inlines(self) -> None:
        engine = _MockEngine(render_return="inlined alice")
        paging = PagingPolicy()  # members.item not listed
        processor = MoodViewProcessorImpl(engine=engine, paging=paging)  # type: ignore[arg-type]
        member = self._member()
        result = processor("member.md", member)

        assert engine.rendered == [("member.md", member)]
        assert engine.written == []
        assert result == "inlined alice"


class TestMoodViewProcessorImplNonNodeInlines:
    """Only a real data-tree node can split; any non-node subject (a plain
    dict or list, not wrapped with an anchor path) always inlines."""

    def test_plain_dict_inlines(self) -> None:
        engine = _MockEngine(render_return="inlined")
        processor = MoodViewProcessorImpl(engine=engine)  # type: ignore[arg-type]
        result = processor("summary.md", {"id": "alice", "name": "Alice"})

        assert engine.rendered == [("summary.md", {"id": "alice", "name": "Alice"})]
        assert engine.written == []
        assert result == "inlined"

    def test_plain_list_inlines(self) -> None:
        engine = _MockEngine(render_return="inlined")
        processor = MoodViewProcessorImpl(engine=engine)  # type: ignore[arg-type]
        result = processor("list.md", [{"id": "a"}, {"id": "b"}])

        assert engine.rendered == [("list.md", [{"id": "a"}, {"id": "b"}])]
        assert engine.written == []
        assert result == "inlined"


class TestMoodViewProcessorImplPagePath:
    """A split subject maps to its output path via ``PagingPolicy.page_path``
    (paging C3), so its directory is the view name."""

    _TREE = {"members": [{"id": "alice", "name": "Alice"}]}

    def test_tree_node_uses_anchor_derived_page_path(self) -> None:
        engine = _MockEngine()
        paging = PagingPolicy(("members.item",))
        processor = MoodViewProcessorImpl(engine=engine, paging=paging)  # type: ignore[arg-type]
        member = wrap_tree(self._TREE)["members"][0]
        processor("member.md", member)

        # Directory is the view name (``members``), not the template stem.
        assert engine.written == [("member.md", member, Path("members/alice.md"))]


class TestMoodViewProcessorImplPageSubject:
    """A scalar is never a real node, so it can never split and inlines."""

    def test_scalar_inlines(self) -> None:
        engine = _MockEngine(render_return="hello")
        processor = MoodViewProcessorImpl(engine=engine)  # type: ignore[arg-type]
        result = processor("x.md", "just a string")

        assert engine.rendered == [("x.md", "just a string")]
        assert engine.written == []
        assert result == "hello"


class TestMoodViewProcessorImplViaEngine:
    """End-to-end via a real TemplateEngine — exercises the integration."""

    _TREE = {"members": [{"id": "alice", "name": "Alice"}]}

    def _make_engine(
        self,
        tmp_path: Path,
        templates: dict[str, str],
        paging: PagingPolicy = PagingPolicy(),
    ) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        for name, body in templates.items():
            (templates_dir / name).write_text(body)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        return TemplateEngine(
            out_dir,
            templates_dir=templates_dir,
            output_format=MD,
            filters={},
            paging=paging,
        )

    def test_writes_file_with_rendered_content(self, tmp_path: Path) -> None:
        paging = PagingPolicy(("members.item",))
        engine = self._make_engine(tmp_path, {"profile.md": "hi {{ id }}"}, paging)
        processor = MoodViewProcessorImpl(engine=engine, paging=paging)
        processor("profile.md", wrap_tree(self._TREE)["members"][0])

        # The split page opens with the subject node's own anchor (C9).
        assert (tmp_path / "out" / "members" / "alice.md").read_text() == (
            '<a id="/members/alice"></a>\nhi alice'
        )

    def test_non_node_dict_does_not_write_file(self, tmp_path: Path) -> None:
        # A non-node dict inlines, so no page is written.
        engine = self._make_engine(tmp_path, {"profile.md": "hi {{ id }}"})
        processor = MoodViewProcessorImpl(engine=engine)
        result = processor("profile.md", {"id": "alice"})

        assert result == "hi alice"
        assert not (tmp_path / "out" / "profile" / "alice.md").exists()
