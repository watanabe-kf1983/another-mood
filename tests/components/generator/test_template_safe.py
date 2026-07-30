"""Structural audit that the ``TemplateSafe`` types expose no capability path
to a template.

Each type is a case of :class:`TestSurfaceAudit`, whose reference surface adapts
to the case's shape. ``Markup`` is not audited here — its safety depends on how
the engine exposes it, so it falls to the live-render SSTI test (task P11).
"""

import dataclasses
from abc import ABC
from typing import final

import pytest
from markupsafe import Markup

from another_mood.components.generator.data_tree import ArrayNode, MappingNode
from another_mood.components.generator.data_tree_filters import MissingNode
from another_mood.components.generator.inert import (
    InertArray,
    InertMapping,
    ensure_inert,
)
from another_mood.components.generator.template_safe import ensure_template_safe

_ROOT = MappingNode({}, parent=None, segment="", type_index={})

_CASES = [
    pytest.param(InertMapping(), id="InertMapping"),
    pytest.param(InertArray(), id="InertArray"),
    pytest.param(_ROOT, id="MappingNode"),
    pytest.param(
        ArrayNode([], parent=_ROOT, segment="", type_index={}), id="ArrayNode"
    ),
    pytest.param(MissingNode(anchor_path="/unresolved/ref"), id="MissingNode"),
]

# `__init__` is unreachable from a template, so it is trusted on every case.
_INTENDED_BODY_DUNDERS = {"__init__"}

# `__str__` IS invoked when a template stringifies a value, so it is trusted
# per-type, not globally: only MissingNode's renderer hook may define it.
_TYPE_INTENDED_BODY_DUNDERS: dict[type, set[str]] = {MissingNode: {"__str__"}}

# Bases whose body is trusted unaudited (their methods reach only inert
# contents). Explicit, so trust cannot leak to a foreign base behind a subclass.
_TRUSTED_BASES = (dict, list, object, ABC)


class TestSurfaceAudit:
    """Only code review keeps this test — neither the type system nor another
    test catches its deletion."""

    @pytest.mark.parametrize("instance", _CASES)
    def test_public_surface_matches_reference(self, instance: object) -> None:
        assert _reachable_public(instance) == _expected_public_surface(instance)
        # A dataclass's members are data fields, not marshaled elsewhere, so
        # each reachable value must itself be inert.
        if dataclasses.is_dataclass(instance):
            for name in _reachable_public(instance):
                ensure_inert(getattr(instance, name))

    @pytest.mark.parametrize("instance", _CASES)
    def test_foreign_attr_rejected(self, instance: object) -> None:
        with pytest.raises(AttributeError):
            setattr(instance, "pub", "x")

    @pytest.mark.parametrize("instance", _CASES)
    def test_no_unexpected_body_dunder(self, instance: object) -> None:
        # minijinja invokes protocol dunders (attribute access, __getitem__,
        # __call__) while rendering, so an added one could leak a value outside
        # the inert contents. Audited over the whole MRO.
        added = _dunders_added_outside_trusted_bases(type(instance))
        intended = _INTENDED_BODY_DUNDERS | _TYPE_INTENDED_BODY_DUNDERS.get(
            type(instance), set()
        )
        assert added - _generated_dunders(instance) - intended == set()


class TestEnsureTemplateSafe:
    """The render boundary accepts every ``TemplateSafe`` member, by identity
    for the engine-owned ones and by marshaling for data."""

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param(MissingNode(anchor_path="/unresolved/ref"), id="MissingNode"),
            pytest.param(Markup("<b>x</b>"), id="Markup"),
            pytest.param(_ROOT, id="Node"),
            pytest.param(InertMapping(), id="InertMapping"),
        ],
    )
    def test_passes_through_by_identity(self, value: object) -> None:
        assert ensure_template_safe(value) is value

    def test_marshals_raw_data(self) -> None:
        assert ensure_template_safe({"a": [1]}) == InertMapping({"a": InertArray([1])})

    def test_rejects_a_non_template_safe_value(self) -> None:
        with pytest.raises(TypeError, match="Non-inert value"):
            ensure_template_safe(object())


def _dunders_added_outside_trusted_bases(t: type) -> set[str]:
    return {
        name
        for cls in t.__mro__
        if cls not in _TRUSTED_BASES
        for name in vars(cls)
        if _is_dunder(name)
    }


def _expected_public_surface(obj: object) -> set[str]:
    if isinstance(obj, dict):
        return _reachable_public({})
    elif isinstance(obj, list):
        return _reachable_public([])
    elif dataclasses.is_dataclass(obj):
        return {f.name for f in dataclasses.fields(obj)}
    else:
        return set()


def _generated_dunders(obj: object) -> set[str]:
    if dataclasses.is_dataclass(obj):
        return _frozen_dataclass_dunders()
    return _container_dunders()


def _reachable_public(obj: object) -> set[str]:
    # `dir` also lists metaclass members (`mro` / `register`) that raise on the
    # instance, so reachability filters them out.
    return {
        name
        for name in dir(obj)
        if not name.startswith("_") and _is_reachable(obj, name)
    }


def _is_reachable(obj: object, name: str) -> bool:
    try:
        getattr(obj, name)
    except AttributeError:
        return False
    return True


def _container_dunders() -> set[str]:
    """Compiler / metaclass dunders of the inert-container shape, from a
    reference class so the audit stays version-robust."""

    @final
    class _Ref(dict[str, int], ABC):
        __slots__ = ()
        _annotated: int

    return {n for n in vars(_Ref) if _is_dunder(n)}


def _frozen_dataclass_dunders() -> set[str]:
    """The frozen-dataclass counterpart of :func:`_container_dunders`."""

    @final
    @dataclasses.dataclass(frozen=True)
    class _Ref:
        _field: int

    return {n for n in vars(_Ref) if _is_dunder(n)}


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")
