"""Structural lockdown of the four container types the marshal boundary
produces — each audit runs over every type via parametrize."""

from abc import ABC
from typing import final

import pytest

from another_mood.components.generator.data_tree import ArrayNode, MappingNode
from another_mood.components.generator.inert import InertArray, InertMapping

_ROOT = MappingNode({}, parent=None, segment="", type_index={})

_CASES = [
    pytest.param(InertMapping(), id="InertMapping"),
    pytest.param(InertArray(), id="InertArray"),
    pytest.param(_ROOT, id="MappingNode"),
    pytest.param(
        ArrayNode([], parent=_ROOT, segment="", type_index={}), id="ArrayNode"
    ),
]

# Body dunders a class may add, beyond the compiler artifacts _auto_dunders
# covers. Uniform across the four: subtracting a name a class lacks is a no-op.
_INTENDED_BODY_DUNDERS = {"__init__"}

# The only bases trusted without auditing their body — their protocol dunders
# reach nothing but the inert contents. An explicit whitelist, so trust cannot
# leak to a foreign base laundered in behind a subclass.
_TRUSTED_BASES = (dict, list, object, ABC)


class TestSurfaceAudit:
    """The four types add no capability path over a bare dict / list.

    Only code review keeps this test — neither the type system nor another
    test catches its deletion.
    """

    @pytest.mark.parametrize("instance", _CASES)
    def test_public_surface_matches_bare_builtin(self, instance: object) -> None:
        assert _reachable_public(instance) == _expected_public_surface(instance)

    @pytest.mark.parametrize("instance", _CASES)
    def test_no_instance_dict_and_foreign_attr_rejected(self, instance: object) -> None:
        # __slots__ on every base leaves no __dict__ to hold `self.pub = os`.
        assert not hasattr(instance, "__dict__")
        with pytest.raises(AttributeError):
            setattr(instance, "pub", "x")

    @pytest.mark.parametrize("instance", _CASES)
    def test_no_unexpected_dunder_outside_trusted_bases(self, instance: object) -> None:
        # minijinja invokes protocol dunders (attribute access, __getitem__,
        # __call__) while rendering, so an added one could return a value
        # outside the inert contents (spike-verified). Audited over the whole
        # MRO, so a dunder on Node or a laundered foreign base is caught too.
        added = _dunders_added_outside_trusted_bases(type(instance))
        assert added - _auto_dunders() - _INTENDED_BODY_DUNDERS == set()


def _dunders_added_outside_trusted_bases(t: type) -> set[str]:
    """Body dunders of every class in ``t``'s MRO except the trusted bases."""
    return {
        name
        for cls in t.__mro__
        if cls not in _TRUSTED_BASES
        for name in vars(cls)
        if _is_dunder(name)
    }


def _expected_public_surface(obj: object) -> set[str]:
    """The surface ``obj`` may expose: that of the bare dict / list it
    subclasses, or empty for a non-container."""
    if isinstance(obj, dict):
        return _reachable_public({})
    elif isinstance(obj, list):
        return _reachable_public([])
    else:
        return set()


def _reachable_public(obj: object) -> set[str]:
    """Non-``_`` names a template can reach on ``obj``.

    ``dir`` also lists metaclass members (``mro`` / ``register``), but those
    raise on the instance, so reachability filters them to the real surface.
    """
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


def _auto_dunders() -> set[str]:
    """Compiler / metaclass dunders shared by the audited classes' shape
    (``@final``, ``__slots__``, generic base, ABC, an annotation), taken from a
    reference class so the audit stays version-robust."""

    @final
    class _Ref(dict[str, int], ABC):
        __slots__ = ()
        _annotated: int

    return {n for n in vars(_Ref) if _is_dunder(n)}


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")
