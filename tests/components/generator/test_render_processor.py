"""Tests for render_processor — render_filter and RenderProcessorImpl."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from jinja2 import DictLoader, Environment

from another_mood.components.generator.data_tree import MappingNode, wrap_tree
from another_mood.components.generator.inert import (
    InertArray,
    InertMapping,
    ensure_inert_mapping,
)
from another_mood.components.generator.render_processor import RenderProcessorImpl
from another_mood.components.generator.output_formats.md import MD
from another_mood.components.generator.edition import PagingPolicy
from another_mood.components.generator.template_engine import TemplateEngine
from another_mood.components.shared.windows_reserved_name import (
    WindowsReservedNameError,
)
from another_mood.components.shared.user_source.diagnostic import FileValidationError


# -- Helpers --


def _at(root: object, *path: object) -> object:
    """Index a wrapped tree by keys / indices; result feeds ``object``-typed
    subject / this parameters."""
    current = root
    for seg in path:
        if isinstance(current, InertArray):
            assert isinstance(seg, int)
            current = current[seg]
        elif isinstance(current, InertMapping):
            assert isinstance(seg, str)
            current = current[seg]
        else:
            raise AssertionError(f"{current!r} is not indexable at {seg!r}")
    return current


def _wrap(data: Mapping[str, Any]) -> MappingNode:
    """Marshal a raw dict, then anchor it — the two-stage build."""
    return wrap_tree(ensure_inert_mapping(data))


@dataclass
class _MockEngine:
    """Captures calls to render / render_to_file for routing assertions."""

    rendered: list[tuple[str, object]] = field(default_factory=lambda: [])
    written: list[tuple[str, object, Path]] = field(default_factory=lambda: [])
    render_return: str = "INLINED"

    def render(self, template_name: str, subject: object) -> str:
        self.rendered.append((template_name, subject))
        return self.render_return

    def render_to_file(
        self, template_name: str, subject: object, out_path: Path
    ) -> None:
        self.written.append((template_name, subject, out_path))


def _make_filter_env(
    processor: RenderProcessorImpl, templates: dict[str, str] | None = None
) -> Environment:
    env = Environment(keep_trailing_newline=True, loader=DictLoader(templates or {}))
    env.filters["render"] = processor.render_filter  # pyright: ignore[reportArgumentType]
    return env


# -- render_filter --


class TestRenderSubtreeGuard:
    """A node subject must lie within the host ``this``'s subtree; otherwise
    the render raises a build error (B12)."""

    _TREE = {
        "albums": [{"id": "a1", "title": "A1"}],
        "prose": [{"id": "p1", "content": "note"}],
    }

    def _render(self, this: object, subject: object) -> tuple[_MockEngine, str]:
        engine = _MockEngine(render_return="OK")
        env = _make_filter_env(RenderProcessorImpl(engine=engine))
        result = env.from_string('{{ subject | render("x.md") }}').render(
            this=this, subject=subject
        )
        return engine, result

    def test_descendant_subject_passes(self) -> None:
        tree = _wrap(self._TREE)
        engine, result = self._render(this=tree, subject=_at(tree, "albums", 0))

        assert result == "OK"
        assert engine.rendered == [("x.md", _at(tree, "albums", 0))]

    def test_subject_equal_to_host_passes(self) -> None:
        tree = _wrap(self._TREE)
        album = _at(tree, "albums", 0)
        _, result = self._render(this=album, subject=album)

        assert result == "OK"

    def test_non_descendant_subject_raises(self) -> None:
        tree = _wrap(self._TREE)
        with pytest.raises(FileValidationError) as exc:
            self._render(
                this=_at(tree, "albums", 0),
                subject=_at(tree, "prose", 0),
            )
        (diag,) = exc.value.diagnostics
        assert diag.source == "render"
        # The error names both the off-subtree subject and the host.
        assert "/prose/p1" in diag.message
        assert "/albums/a1" in diag.message

    def test_sibling_whose_name_prefixes_host_is_rejected(self) -> None:
        # `/album_tracklist/x` is a sibling of `/album`, not a descendant, even
        # though its anchor path string-prefixes the host's -- ancestry is by
        # identity, so a prefix shortcut would wrongly accept it.
        tree = _wrap({"album": {"id": "a"}, "album_tracklist": [{"id": "x"}]})
        with pytest.raises(FileValidationError):
            self._render(
                this=_at(tree, "album"),
                subject=_at(tree, "album_tracklist", 0),
            )

    def test_non_node_subject_is_exempt(self) -> None:
        # A string carries no anchor and no page identity, so it is exempt even
        # under a node host.
        tree = _wrap(self._TREE)
        engine, result = self._render(
            this=_at(tree, "albums", 0), subject="just a string"
        )

        assert result == "OK"
        assert engine.rendered == [("x.md", "just a string")]

    def test_node_subject_under_non_node_host_raises(self) -> None:
        # A real node cannot be a descendant of a non-node host.
        tree = _wrap(self._TREE)
        with pytest.raises(FileValidationError):
            self._render(this="not a node", subject=_at(tree, "albums", 0))


class TestRenderFilter:
    """Only the filter's own wiring: routing to the processor and guard.
    The routing decisions themselves (split / inline / paths) are covered
    by the RenderProcessorImpl tests, the guard semantics above."""

    def test_dispatches_template_name_and_subject(self) -> None:
        engine = _MockEngine(render_return="OUT")
        processor = RenderProcessorImpl(engine=engine)
        env = _make_filter_env(processor)
        result = env.from_string('{{ user | render("profile.md") }}').render(
            user={"id": "alice", "name": "Alice"}
        )

        assert result == "OUT"
        assert engine.rendered == [("profile.md", {"id": "alice", "name": "Alice"})]

    def test_guard_error_points_at_template_without_line(self) -> None:
        """The guard fires with the host ``this`` resolved from context; a
        filter has no source line, so the diagnostic carries only the
        enclosing template's name."""
        tree = _wrap({"albums": [{"id": "a1"}], "prose": [{"id": "p1"}]})
        processor = RenderProcessorImpl(engine=_MockEngine())
        env = _make_filter_env(processor, {"page.md": '{{ subject | render("x.md") }}'})
        with pytest.raises(FileValidationError) as exc:
            env.get_template("page.md").render(
                this=_at(tree, "albums", 0), subject=_at(tree, "prose", 0)
            )
        (diag,) = exc.value.diagnostics
        assert diag.file == Path("page.md")
        assert diag.line is None
        assert diag.source == "render"
        assert "/prose/p1" in diag.message
        assert "/albums/a1" in diag.message


class TestRenderFilterViaEngine:
    """End-to-end via a real TemplateEngine — the filter is registered by
    the engine itself, and its output survives the format's finalize."""

    _TREE = {"members": [{"id": "alice", "name": "A*B"}]}

    def _make_engine(
        self,
        tmp_path: Path,
        templates: dict[str, str],
        filters: dict[str, Any] | None = None,
    ) -> TemplateEngine:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)
        for name, body in templates.items():
            (templates_dir / name).write_text(body)
        out_dir = tmp_path / "out"
        out_dir.mkdir(parents=True)
        return TemplateEngine(
            out_dir,
            templates_dir=templates_dir,
            output_format=MD,
            filters=filters or {},
        )

    def test_inline_output_is_not_escaped_again(self, tmp_path: Path) -> None:
        """The subtemplate's rendered markdown passes through the outer
        template's finalize untouched: its markup is not re-escaped, while
        the value interpolated inside it is escaped exactly once."""
        engine = self._make_engine(
            tmp_path,
            {
                "index.md": '{{ this.members[0] | render("member.md") }}',
                "member.md": "**{{ name }}**",
            },
        )
        result = engine.render("index.md", _wrap(self._TREE))

        assert "**A\\*B**" in result

    def test_engine_owned_filter_beats_caller_supplied_one(
        self, tmp_path: Path
    ) -> None:
        """``render`` is part of the engine's vocabulary: a caller-supplied
        filter of the same name must not shadow it."""

        def hijack(*args: object) -> str:
            return "HIJACKED"

        engine = self._make_engine(
            tmp_path,
            {
                "index.md": '{{ this.members[0] | render("member.md") }}',
                "member.md": "real {{ id }}",
            },
            filters={"render": hijack},
        )
        result = engine.render("index.md", _wrap(self._TREE))

        assert "real alice" in result
        assert "HIJACKED" not in result


# -- RenderProcessorImpl --


class TestRenderProcessorImplFilePerRouting:
    """A real node's split-vs-inline decision follows ``file_per`` (C4)."""

    _TREE = {"members": [{"id": "alice", "name": "Alice"}]}

    def _member(self) -> object:
        return _at(_wrap(self._TREE), "members", 0)

    def test_node_in_file_per_splits(self) -> None:
        engine = _MockEngine()
        paging = PagingPolicy(("members.item",))
        processor = RenderProcessorImpl(engine=engine, paging=paging)
        member = self._member()
        result = processor("member.md", member)

        assert engine.written == [("member.md", member, Path("members/alice.md"))]
        assert engine.rendered == []
        assert result == ""

    def test_node_absent_from_file_per_inlines(self) -> None:
        engine = _MockEngine(render_return="inlined alice")
        paging = PagingPolicy()  # members.item not listed
        processor = RenderProcessorImpl(engine=engine, paging=paging)
        member = self._member()
        result = processor("member.md", member)

        assert engine.rendered == [("member.md", member)]
        assert engine.written == []
        assert result == "inlined alice"


class TestRenderProcessorImplNonNodeInlines:
    """Only a real data-tree node can split; any non-node subject (a plain
    dict or list, not wrapped with an anchor path) always inlines."""

    def test_plain_dict_inlines(self) -> None:
        engine = _MockEngine(render_return="inlined")
        processor = RenderProcessorImpl(engine=engine)
        result = processor("summary.md", {"id": "alice", "name": "Alice"})

        assert engine.rendered == [("summary.md", {"id": "alice", "name": "Alice"})]
        assert engine.written == []
        assert result == "inlined"

    def test_plain_list_inlines(self) -> None:
        engine = _MockEngine(render_return="inlined")
        processor = RenderProcessorImpl(engine=engine)
        result = processor("list.md", [{"id": "a"}, {"id": "b"}])

        assert engine.rendered == [("list.md", [{"id": "a"}, {"id": "b"}])]
        assert engine.written == []
        assert result == "inlined"


class TestRenderProcessorImplPagePath:
    """A split subject maps to its output path via ``PagingPolicy.page_path``
    (paging C3), so its directory is the view name."""

    _TREE = {"members": [{"id": "alice", "name": "Alice"}]}

    def test_tree_node_uses_anchor_derived_page_path(self) -> None:
        engine = _MockEngine()
        paging = PagingPolicy(("members.item",))
        processor = RenderProcessorImpl(engine=engine, paging=paging)
        member = _at(_wrap(self._TREE), "members", 0)
        processor("member.md", member)

        # Directory is the view name (``members``), not the template stem.
        assert engine.written == [("member.md", member, Path("members/alice.md"))]


class TestRenderProcessorImplReservedName:
    """A split node whose id yields a filesystem-reserved page segment is
    rejected before any file is written (C7)."""

    def test_reserved_id_raises(self) -> None:
        engine = _MockEngine()
        paging = PagingPolicy(("members.item",))
        processor = RenderProcessorImpl(engine=engine, paging=paging)
        # `CON` is a Windows device name: `members/CON.md` writes to the
        # console, not a file, so the page is rejected on every OS.
        member = _at(_wrap({"members": [{"id": "CON"}]}), "members", 0)
        with pytest.raises(WindowsReservedNameError):
            processor("member.md", member)
        assert engine.written == []


class TestRenderProcessorImplPageSubject:
    """A scalar is never a real node, so it can never split and inlines."""

    def test_scalar_inlines(self) -> None:
        engine = _MockEngine(render_return="hello")
        processor = RenderProcessorImpl(engine=engine)
        result = processor("x.md", "just a string")

        assert engine.rendered == [("x.md", "just a string")]
        assert engine.written == []
        assert result == "hello"


class TestRenderProcessorImplViaEngine:
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
        processor = RenderProcessorImpl(engine=engine, paging=paging)
        processor("profile.md", _at(_wrap(self._TREE), "members", 0))

        # The split page opens with the subject node's own anchor (C9).
        assert (tmp_path / "out" / "members" / "alice.md").read_text() == (
            '<a id="/members/alice"></a>\nhi alice'
        )

    def test_non_node_dict_does_not_write_file(self, tmp_path: Path) -> None:
        # A non-node dict inlines, so no page is written.
        engine = self._make_engine(tmp_path, {"profile.md": "hi {{ id }}"})
        processor = RenderProcessorImpl(engine=engine)
        result = processor("profile.md", {"id": "alice"})

        assert result == "hi alice"
        assert not (tmp_path / "out" / "profile" / "alice.md").exists()
