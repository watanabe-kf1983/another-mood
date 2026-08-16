"""Build info — one invocation's facts, flattened for templates to query by key."""

from collections.abc import Mapping
from types import MappingProxyType

type BuildInfo = Mapping[str, str]

NO_BUILD_INFO: BuildInfo = MappingProxyType({})
"""What a caller with no store to supply passes."""


def flatten_build_info(prefix: str, values: Mapping[str, object]) -> BuildInfo:
    """Project ``values`` onto ``prefix``-dotted keys, dropping the unset ones.

    An unset value (``None``) yields no key at all, so a template querying it
    falls back to the default it passed rather than reading ``"None"``.
    """
    return {
        f"{prefix}.{name}": _render_value(value)
        for name, value in values.items()
        if value is not None
    }


def _render_value(value: object) -> str:
    """Render one value as the store's string, in the sources' own idiom."""
    if isinstance(value, bool):
        # Python's "True" would be the only capitalized spelling on a page
        # whose other values come from YAML.
        return "true" if value else "false"
    else:
        return str(value)
