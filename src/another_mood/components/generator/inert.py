"""The inert value model and the marshal boundary that produces it.

A value is *inert* when it carries no path to a host capability, so it is safe
to expose to a template.  :func:`ensure_inert` (and its ``_mapping`` /
``_array`` variants) is the boundary every ``object -> inert`` crossing goes
through; everything downstream takes ``InertValue`` and never sees raw
``object``.
"""

from collections.abc import Mapping
from typing import Any, NoReturn, cast


type InertValue = str | int | float | bool | None | InertMapping | InertArray
"""The values a wrapped data tree may hold — scalars and inert containers.

The element type of :class:`InertMapping` / :class:`InertArray` and the result
type of marshaling.
"""


class InertMapping(dict[str, "InertValue"]):
    """An ``InertValue``-valued mapping — anchor-less base of ``MappingNode``.

    Read-only after construction: every non-dunder ``dict`` mutator raises.
    Construction-time filling goes through ``__setitem__``, which stays open.
    """

    __slots__ = ()

    def clear(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "clear")

    def pop(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "pop")

    def popitem(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "popitem")

    def setdefault(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "setdefault")

    def update(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "update")


class InertArray(list["InertValue"]):
    """An ``InertValue``-valued list — anchor-less base of ``ArrayNode``.

    Read-only after construction: every non-dunder ``list`` mutator raises.
    Construction-time filling goes through ``list.append``, which stays open.
    """

    __slots__ = ()

    def append(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "append")

    def clear(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "clear")

    def extend(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "extend")

    def insert(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "insert")

    def pop(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "pop")

    def remove(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "remove")

    def reverse(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "reverse")

    def sort(self, *args: object, **kwargs: object) -> NoReturn:
        _reject_mutation(self, "sort")


def _reject_mutation(container: object, method: str) -> NoReturn:
    """Raise on a container mutator: the data tree is shared across every
    page's render, and any non-``_`` method is callable from a template."""
    raise TypeError(
        f"{type(container).__name__}.{method}() is disabled: the data tree is read-only"
    )


def ensure_inert(value: object) -> InertValue:
    """Marshal any ``object`` to inert: dispatch a container to the typed
    marshaler, pass an exact scalar, else raise.

    For a value whose static type is only ``object``; a caller holding a
    ``Mapping`` / ``list`` uses :func:`ensure_inert_mapping` /
    :func:`ensure_inert_array` to keep the concrete return type.
    """
    if isinstance(value, Mapping):
        return ensure_inert_mapping(cast(Mapping[str, Any], value))
    elif isinstance(value, list):
        return ensure_inert_array(cast("list[Any]", value))
    else:
        return _inert_scalar(value)


def ensure_inert_mapping(data: Mapping[str, Any]) -> InertMapping:
    """Marshal a mapping to an ``InertMapping``: repack a raw ``dict`` (raising
    on a non-inert leaf), or return an already-inert mapping unchanged — so an
    anchored ``MappingNode`` keeps its identity.
    """
    if isinstance(data, InertMapping):
        return data
    return InertMapping({k: ensure_inert(v) for k, v in data.items()})


def ensure_inert_array(items: list[Any]) -> InertArray:
    """Marshal a list to an ``InertArray`` — the list counterpart of
    :func:`ensure_inert_mapping`.
    """
    if isinstance(items, InertArray):
        return items
    return InertArray([ensure_inert(v) for v in items])


# bool before int: bool is an int subclass, so an isinstance test for int
# would also match a bool and normalize it to 0 / 1.
_SCALAR_TYPES = (bool, int, float, str)


def _inert_scalar(value: Any) -> InertValue:
    """Accept an ``InertValue`` scalar leaf (str/int/float/bool/None),
    normalizing a scalar *subclass* to its exact type; raise on anything else.
    The one runtime check backing the ``[InertValue]`` element type.
    """
    if value is None:
        return value
    for scalar_type in _SCALAR_TYPES:
        if isinstance(value, scalar_type):
            return value if type(value) is scalar_type else scalar_type(value)
    raise TypeError(
        f"Non-inert value of type {type(value).__name__!r} reached "
        f"the data tree: {value!r}"
    )
