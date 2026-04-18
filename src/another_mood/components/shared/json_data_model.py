"""JSON data model — merge strategy for multiple data sources.

See: dev-docs/contents/internal/json-data-model.md
"""

from functools import reduce
from pathlib import Path
from typing import Any

import yaml

type JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


def load_yamls(*directories: Path) -> dict[str, Any]:
    """Load all YAML files from directories and deep-merge into a single dict.

    Directories that do not exist are silently skipped.
    """
    docs: list[dict[str, Any]] = []
    for directory in directories:
        if not directory.exists():
            continue
        for f in sorted(directory.rglob("*.yaml")):
            loaded: object = yaml.safe_load(f.read_text())
            if not isinstance(loaded, dict):
                raise ValueError(
                    f"Expected a YAML mapping in {f}, got {type(loaded).__name__}"
                )
            docs.append(loaded)  # type: ignore[arg-type]
    return reduce(deep_merge, docs, {})


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two JSON objects following the project merge strategy.

    - Objects: recursive merge
    - Arrays: concatenation (order is not significant; Generator
      sorts by id etc. for final output)
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
