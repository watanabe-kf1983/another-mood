"""JSON data model — load and save the project's YAML representation.

See: dev-docs/contents/internal/json-data-model.md

Reads use ``load_model`` (deep-merge across multiple files / dirs).
Writes use ``save_model`` (single-file emit applying the project's
serialization conventions: YAML 1.2, literal-block multiline strings,
None-key elision).
"""

from functools import reduce
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter

from another_mood.components.shared.file_type import FileType

type JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


# ── Read ─────────────────────────────────────────────────────────────


def load_model(*paths: Path) -> dict[str, Any]:
    """Load YAML files from each path and deep-merge into a single dict.

    Files are loaded in path-sorted order so the merged result is
    deterministic regardless of filesystem iteration order.
    """
    files = sorted(collect_files(*paths))
    return reduce(deep_merge, (_load_mapping(f) for f in files), {})


def collect_files(*paths: Path) -> list[Path]:
    """Expand each path argument into a list of files.

    Each path may be a file (included as-is), a directory (recursively
    scanned), or a missing path (skipped).
    """
    files: list[Path] = []
    for p in paths:
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(f for f in p.rglob("*") if f.is_file())
    return files


def _load_mapping(path: Path) -> dict[str, Any]:
    """Parse path as a YAML 1.2 mapping; return {} for non-YAML files.

    A fresh YAML instance is created per call (see ``save_model`` for
    the thread-safety rationale).  ``typ='safe'`` returns plain Python
    types (dict / list / scalar) — round-trip mode is not needed here.
    """
    if FileType.YAML.match(path):
        loaded: object = YAML(typ="safe").load(path.read_text())  # type: ignore[no-untyped-call]
        if not isinstance(loaded, dict):
            raise ValueError(
                f"Expected a YAML mapping in {path}, got {type(loaded).__name__}"
            )
        return loaded  # type: ignore[return-value]
    return {}


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


# ── Write ────────────────────────────────────────────────────────────


def save_model(path: Path, data: object) -> None:
    """Write `data` as YAML 1.2 to `path`.

    Applies the project's serialization conventions:

    * Multiline strings render as literal block scalars (|).
    * None-valued keys are dropped recursively per the
      "nullable は項目自体を省略する" rule (json-data-model.md):
      leaving nulls in the output makes Jinja2 templates render
      the string "None".

    A fresh ruamel YAML instance is created per call because
    ``YAML()`` is not thread-safe — its emitter/serializer internal
    state is shared across calls, and concurrent dumps from different
    pipeline-stage watcher threads corrupt each other's state (e.g.
    "ValueError: I/O operation on closed file").
    """
    yaml_writer = YAML()
    yaml_writer.Representer = _LiteralStrRepresenter
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml_writer.dump(_drop_nones(data), f)  # type: ignore[reportUnknownMemberType]


class _LiteralStrRepresenter(RoundTripRepresenter):
    """Represent multiline strings as literal block scalars (|)."""

    def represent_str(self, data: str) -> object:
        if "\n" in data:
            return self.represent_scalar("tag:yaml.org,2002:str", data, style="|")  # type: ignore[reportUnknownMemberType]
        return super().represent_str(data)  # type: ignore[reportUnknownMemberType]


# Exact-type registration overrides RoundTripRepresenter's default str
# representer; multi-registration additionally covers str subclasses
# (e.g. UserStr from preprocess.validator) via MRO lookup.
_LiteralStrRepresenter.add_representer(str, _LiteralStrRepresenter.represent_str)  # type: ignore[reportUnknownMemberType]
_LiteralStrRepresenter.add_multi_representer(str, _LiteralStrRepresenter.represent_str)  # type: ignore[reportUnknownMemberType]


def _drop_nones(d: Any) -> Any:  # noqa: ANN401
    """Recursively drop None-valued keys from dicts in a serialized tree."""
    if isinstance(d, dict):
        return {k: _drop_nones(v) for k, v in d.items() if v is not None}  # type: ignore[reportUnknownVariableType]
    if isinstance(d, list):
        return [_drop_nones(v) for v in d]  # type: ignore[reportUnknownVariableType]
    return d
