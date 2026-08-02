"""Live-render SSTI regression: pins how minijinja exposes what it is handed.

The marshal contract (see ``template_safe`` / ``inert``) is sound only under a
set of exposure rules that belong to the engine, not to us: dunders are sealed,
``_``-prefixed members are refused, and non-``_`` members of a wrapped object
are reachable and callable.  Those rules hold in the current minijinja and can
change in a future one, so they are pinned here by firing payloads at a real
render.  The payloads are classic, publicly documented SSTI shapes.

Two directions are pinned, and both matter:

- what is **sealed** — a payload that must not reach a host capability;
- what is **exposed by design** — the hazards the contract is built around.  A
  red test there is not a breach but a signal that the engine grew stricter and
  the contract may relax.

Exposure is the engine's layer, so these render through ``make_environment``
directly rather than through ``TemplateEngine``: the render boundary would
refuse to bind a hostile object in the first place (covered in
``test_template_engine``), which is the very case this test has to reason past.
``TemplateEngine`` is used only where the payload targets the loader.
"""

from pathlib import Path

import pytest
from markupsafe import Markup
from minijinja import TemplateError

from another_mood.components.generator.data_tree import MappingNode
from another_mood.components.generator.inert import ensure_inert_array
from another_mood.components.generator.output_formats.md import MD
from another_mood.components.generator.template_engine import (
    OutputFormat,
    TemplateEngine,
    make_environment,
)
from another_mood.components.shared.user_source.diagnostic import FileValidationError

# Escaping is orthogonal to exposure, and md's would obscure the assertions.
_PLAIN = OutputFormat(name="plain", escape=lambda s: s)


class _Capability:
    """Stand-in for a host capability a payload wants to reach — its call is
    recorded rather than doing anything, so a breach shows up as a marker
    instead of as a real side effect."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self) -> str:
        self.calls.append("run")
        return "REACHED"


class _HostileMapping(dict[str, object]):
    """What the marshal contract exists to keep out: a container whose non-``_``
    surface reaches a capability.  Never built by the tool — only the contract
    keeps it away from a template, so the engine's own behavior around one is
    what this test measures."""

    def __init__(self, capability: _Capability) -> None:
        super().__init__({"a": 1})
        self.capability = capability

    def danger(self) -> str:
        return self.capability.run()

    def _hidden(self) -> str:
        return self.capability.run()


def _render(source: str, **context: object) -> str:
    return make_environment(_PLAIN).render_str(source, **context)


class TestDunderPathSealed:
    """The Jinja2 SSTI root — reflection from any object into the class graph —
    is structurally absent: minijinja's value model has no dunders."""

    @pytest.mark.parametrize(
        "source",
        [
            "{{ this.__class__ }}",
            "{{ this['__class__'] }}",
            "{{ this.__init__ }}",
            "{{ this.__getitem__ }}",
            "{{ this.__dict__ }}",
            "{{ this.__setattr__ }}",
            "{{ text.__class__ }}",
            "{{ func.__globals__ }}",
        ],
    )
    def test_dunder_access_yields_undefined(self, source: str) -> None:
        capability = _Capability()
        assert (
            _render(
                source,
                this=_HostileMapping(capability),
                text="x",
                func=lambda: None,
            )
            == ""
        )
        assert capability.calls == []

    def test_class_graph_walk_fails_instead_of_resolving(self) -> None:
        # The classic `''.__class__.__mro__[1].__subclasses__()` chain: each
        # step is undefined, and calling a method on undefined is an error.
        with pytest.raises(TemplateError):
            _render("{{ this.__class__.__mro__[1].__subclasses__() }}", this={})


class TestAttributeFilterTraversalSealed:
    """The string-named attribute filters are the sanctioned way around a
    parser-level dunder ban, so each is fired separately."""

    def test_attr_cannot_fetch_a_dunder(self) -> None:
        assert _render("{{ this | attr('__class__') }}", this={"a": 1}) == ""

    def test_map_attribute_cannot_fetch_a_dunder(self) -> None:
        assert (
            _render("{{ [this] | map(attribute='__class__') | list }}", this={"a": 1})
            == "[None]"
        )

    def test_selectattr_cannot_fetch_a_dunder(self) -> None:
        assert _render("{{ [this] | selectattr('__class__') | list }}", this={}) == "[]"

    def test_groupby_cannot_fetch_a_dunder(self) -> None:
        # The record still groups, but under a key that resolved to nothing.
        rendered = _render("{{ [this] | groupby('__class__') | list }}", this={"a": 1})
        assert "class" not in rendered


class TestFormatStringFamilySealed:
    """`str.format` / `format_map` reach attributes through a *data* string in
    Python, which turns any format string into a traversal primitive.  Neither
    minijinja's string method nor its filter carries that power."""

    def test_format_method_has_no_attribute_traversal(self) -> None:
        with pytest.raises(TemplateError):
            _render("{{ '{0.__class__}'.format(this) }}", this={"a": 1})

    def test_format_map_does_not_exist(self) -> None:
        with pytest.raises(TemplateError):
            _render("{{ '{a}'.format_map(this) }}", this={"a": 1})

    def test_format_filter_treats_a_traversal_field_as_text(self) -> None:
        # The filter is printf-style, so a brace field is not a field at all.
        assert (
            _render("{{ '{0.__class__}' | format(this) }}", this={}) == "{0.__class__}"
        )


class TestReservedPrefixDenied:
    """The data tree keeps its parent link and metadata in ``_``-prefixed
    attributes, and minijinja's refusal of those is what keeps a template from
    walking out of the value it was given into ``_NodeMeta`` — a plain Python
    object that was never marshaled."""

    def _node(self) -> MappingNode:
        return MappingNode({"title": "T"}, parent=None, segment="", type_index={})

    @pytest.mark.parametrize(
        "source", ["{{ this._parent }}", "{{ this._meta }}", "{{ this['_meta'] }}"]
    )
    def test_reserved_attribute_is_undefined(self, source: str) -> None:
        assert _render(source, this=self._node()) == ""

    def test_reserved_method_call_is_refused(self) -> None:
        with pytest.raises(TemplateError, match="insecure method call"):
            _render("{{ this._children() }}", this=self._node())

    def test_a_data_field_still_resolves(self) -> None:
        # The control: refusal is about the `_` prefix, not about node access.
        assert _render("{{ this.title }}", this=self._node()) == "T"


class TestExposedByDesign:
    """The hazards the marshal contract is built around.  These pass while the
    engine still exposes them; a failure here means minijinja grew stricter, and
    the contract can be relaxed — not that anything is broken."""

    def test_a_non_underscore_method_is_callable(self) -> None:
        capability = _Capability()
        assert _render("{{ this.danger() }}", this=_HostileMapping(capability)) == (
            "REACHED"
        )
        assert capability.calls == ["run"]

    def test_attr_reaches_the_same_method(self) -> None:
        # `attr` is not a second hole but the same one by another spelling:
        # what it fetches is callable too.
        capability = _Capability()
        assert _render(
            "{{ (this | attr('danger'))() }}", this=_HostileMapping(capability)
        ) == ("REACHED")
        assert capability.calls == ["run"]

    def test_a_non_underscore_attribute_is_readable(self) -> None:
        # And what it yields keeps being traversable — reaching the capability
        # object itself is enough, the call needs no further hole.
        capability = _Capability()
        assert _render(
            "{{ this.capability.run() }}", this=_HostileMapping(capability)
        ) == ("REACHED")

    def test_an_underscore_method_is_refused(self) -> None:
        capability = _Capability()
        with pytest.raises(TemplateError, match="insecure method call"):
            _render("{{ this._hidden() }}", this=_HostileMapping(capability))
        assert capability.calls == []

    def test_an_underscore_named_global_is_not_protected(self) -> None:
        # The `_` prefix guards *attributes*, not global names: a capability
        # registered as a global is reachable however it is named.  This is why
        # the engine registers only template helpers as globals.
        capability = _Capability()
        env = make_environment(_PLAIN)
        env.add_global("_capability", capability)
        assert env.render_str("{{ _capability.run() }}") == "REACHED"

    def test_a_registered_filter_is_not_reachable_as_a_value(self) -> None:
        # Filters live in their own namespace, so a helper registered as one
        # cannot be picked up and traversed the way a global can.
        def shout(value: object) -> str:
            return str(value).upper()

        env = make_environment(_PLAIN)
        env.add_filter("shout", shout)
        assert env.render_str("{{ shout }}") == ""


class TestContainerMutatorsSealed:
    """The wrap-side exposure (``TestExposedByDesign``) reaches the dict/list
    mutators too, and the tree is shared across every page's render — so the
    inert containers define them to raise (see ``inert``).  Pinned live: the
    reachability is the engine's rule, the refusal is ours, and what must
    hold is their composition — an explicit error and an intact tree.  The
    error crosses the render as the raw ``TypeError``: a Python exception
    from a method is not wrapped in a ``TemplateError`` (the same engine
    behavior ``TemplateEngine._render`` notes for filter exceptions)."""

    def test_a_mapping_mutator_raises_and_the_tree_is_intact(self) -> None:
        node = MappingNode({"title": "T"}, parent=None, segment="", type_index={})
        with pytest.raises(TypeError, match="read-only"):
            _render("{{ this.pop('title') }}", this=node)
        assert node == {"title": "T"}

    def test_an_array_mutator_raises_and_the_tree_is_intact(self) -> None:
        items = ensure_inert_array([1, 2])
        with pytest.raises(TypeError, match="read-only"):
            _render("{{ this.append(3) }}", this=items)
        assert items == [1, 2]


class TestMarkupExposure:
    """``Markup`` is the one ``TemplateSafe`` member the structural audit could
    not settle on its own (its surface is a Python ``str`` subclass's), because
    what a template sees depends on how the engine marshals it.  It is
    *converted* to a native string, so no Python member survives the crossing."""

    @pytest.mark.parametrize(
        "source",
        [
            "{{ m.__html__() }}",
            "{{ m.unescape() }}",
            "{{ m.striptags() }}",
        ],
    )
    def test_python_str_subclass_members_do_not_survive(self, source: str) -> None:
        with pytest.raises(TemplateError, match="unknown method"):
            _render(source, m=Markup("<b>x</b>"))

    def test_it_is_a_plain_string_to_the_template(self) -> None:
        assert _render("{{ m is string }}", m=Markup("<b>x</b>")) == "True"

    def test_it_still_reaches_finalize_unescaped(self) -> None:
        # The conversion does not cost Markup its purpose: the finalizer sees
        # the Python value and passes it through without escaping.
        env = make_environment(MD)
        assert env.render_str("{{ m }}", m=Markup("<b>|</b>")) == "<b>|</b>"


class TestLoaderConfinement:
    """A template names its includes and its render targets, so the loader is
    the one place a template picks a *path*.  It stays inside the project's
    template directory."""

    def _engine(self, tmp_path: Path, body: str) -> TemplateEngine:
        # The target exists on disk, one directory up: what stops it is the
        # loader refusing the path, not the file being absent.
        outside = tmp_path / "outside.md"
        outside.write_text("OUTSIDE")
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "sibling.md").write_text("SIBLING")
        (templates_dir / "t.md").write_text(body)
        return TemplateEngine(
            tmp_path / "out",
            templates_dir=templates_dir,
            output_format=_PLAIN,
            filters={},
        )

    @pytest.mark.parametrize(
        "body",
        [
            '{% include "../outside.md" %}',
            '{% extends "../outside.md" %}',
            '{% import "../outside.md" as m %}',
            '{% include "../../../../etc/passwd" %}',
            '{{ this | render("../outside.md") }}',
        ],
    )
    def test_escaping_the_template_directory_fails(
        self, tmp_path: Path, body: str
    ) -> None:
        engine = self._engine(tmp_path, body)
        with pytest.raises(FileValidationError) as exc_info:
            engine.render("t.md", {"a": 1})
        # The loader never resolved the path: what comes back is a not-found,
        # not the file that is sitting there.
        assert "exist" in exc_info.value.diagnostics[0].message

    def test_an_absolute_path_fails(self, tmp_path: Path) -> None:
        secret = tmp_path / "secret.txt"
        secret.write_text("TOP-SECRET")
        engine = self._engine(tmp_path, f'{{% include "{secret}" %}}')
        with pytest.raises(FileValidationError):
            engine.render("t.md", {})

    def test_a_sibling_template_still_loads(self, tmp_path: Path) -> None:
        # The control: confinement is about leaving the directory, not about
        # including at all.
        engine = self._engine(tmp_path, '{% include "sibling.md" %}')
        assert engine.render("t.md", {}) == "SIBLING"
