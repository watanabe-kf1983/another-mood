"""The inert value model and the marshal boundary that produces it.

A value is *inert* when it carries no path to a host capability, so it is safe
to expose to a template.  :func:`ensure_inert` is the single ``Any`` boundary:
it asserts each leaf is inert and re-types the containers so the fact is
carried in the type.  Everything downstream takes ``InertValue`` and never
sees raw ``Any``.
"""

from collections.abc import Iterable, Mapping
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


def ensure_inert(data: Mapping[str, Any]) -> InertMapping:
    """Assert ``data`` is inert and mark it, repacking into ``InertMapping`` /
    ``InertArray`` and raising on any non-inert leaf.

    The single ``Any`` boundary: ``load_model`` is a deserializer, so its
    product is inert by origin; this checks each leaf (exact scalar, or
    raise) and re-types the containers so the fact is carried in the type.
    """
    return InertMapping({k: _inert_value(v) for k, v in data.items()})


def _inert_value(value: Any) -> InertValue:
    """Repack one value into an inert container (recursively), or assert an
    inert scalar."""
    if isinstance(value, Mapping):
        return InertMapping(
            {k: _inert_value(v) for k, v in cast(Mapping[str, Any], value).items()}
        )
    elif isinstance(value, list):
        return InertArray([_inert_value(v) for v in cast(Iterable[Any], value)])
    else:
        return _inert_scalar(value)


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
