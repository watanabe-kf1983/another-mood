"""The inert value model and the marshal boundary that produces it.

A value is *inert* when it carries no path to a host capability, so it is safe
to expose to a template.  :func:`ensure_inert` (and its ``_mapping`` /
``_array`` variants) is the boundary every ``object -> inert`` crossing goes
through; everything downstream takes ``InertValue`` and never sees raw
``object``.
"""

from collections.abc import Mapping
from typing import Any, cast


type InertValue = str | int | float | bool | None | InertMapping | InertArray
"""The values a wrapped data tree may hold — scalars and inert containers.

The element type of :class:`InertMapping` / :class:`InertArray` and the result
type of marshaling.
"""


class InertMapping(dict[str, "InertValue"]):
    """An ``InertValue``-valued mapping — anchor-less base of ``MappingNode``."""

    __slots__ = ()


class InertArray(list["InertValue"]):
    """An ``InertValue``-valued list — anchor-less base of ``ArrayNode``."""

    __slots__ = ()


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


_SCALAR_TYPES = (str, int, float, bool)


def _inert_scalar(value: Any) -> InertValue:
    """Accept an exact ``InertValue`` scalar leaf (str/int/float/bool/None),
    or raise — the one runtime check backing the ``[InertValue]`` element
    type.  Exact-type, not ``isinstance``, so a scalar subclass cannot slip in.
    """
    if value is None or type(value) in _SCALAR_TYPES:
        return value
    raise TypeError(
        f"Non-inert value of type {type(value).__name__!r} reached "
        f"the data tree: {value!r}"
    )
