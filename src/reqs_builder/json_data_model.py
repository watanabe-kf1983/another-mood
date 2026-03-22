"""JSON data model — merge strategy for multiple data sources.

See: docs-src/contents/internal/json-data-model.md
"""

from typing import Any

type JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two JSON objects following the project merge strategy.

    - Objects: recursive merge
    - Arrays: concatenation
    - Scalars: override wins
    """
    result = dict(base)
    for key, override_val in override.items():
        if key in result:
            result[key] = _merge_values(result[key], override_val)
        else:
            result[key] = override_val
    return result


def _merge_values(base_val: JsonValue, override_val: JsonValue) -> JsonValue:
    if isinstance(base_val, dict) and isinstance(override_val, dict):
        return deep_merge(base_val, override_val)
    if isinstance(base_val, list) and isinstance(override_val, list):
        return [*base_val, *override_val]
    return override_val
