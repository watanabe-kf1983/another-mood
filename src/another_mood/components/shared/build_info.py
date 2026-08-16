"""Build info — one invocation's facts, flattened for templates to query by key."""

from collections.abc import Iterable, Mapping
from itertools import chain
from types import MappingProxyType
from typing import cast

type BuildInfo = Mapping[str, str]

NO_BUILD_INFO: BuildInfo = MappingProxyType({})
"""What a caller with no store to supply passes."""


def flatten_build_info(prefix: str, values: Mapping[str, object]) -> BuildInfo:
    """Project ``values`` onto ``prefix``-dotted keys, nested mappings included.

    An unset value (``None``) yields no key at all, so a template querying it
    falls back to the default it passed rather than reading ``"None"``.
    """
    return dict(_entries(prefix, values))


def _entries(prefix: str, values: Mapping[str, object]) -> Iterable[tuple[str, str]]:
    return chain.from_iterable(
        _entries_under(f"{prefix}.{name}", value)
        for name, value in values.items()
        if value is not None
    )


def _entries_under(key: str, value: object) -> Iterable[tuple[str, str]]:
    if isinstance(value, Mapping):
        return _entries(key, cast(Mapping[str, object], value))
    else:
        return ((key, _render_value(value)),)


def _render_value(value: object) -> str:
    """Render one value as the store's string, in the sources' own idiom."""
    if isinstance(value, bool):
        # Python's "True" would be the only capitalized spelling on a page
        # whose other values come from YAML.
        return "true" if value else "false"
    else:
        return str(value)
