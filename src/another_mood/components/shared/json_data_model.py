"""JSON data model — load and save the project's YAML representation.

See: dev-docs/contents/internal/json-data-model.md

Reads use ``load_model`` (deep-merge across multiple files / dirs).
Writes use ``save_model`` (single-file emit applying the project's
serialization conventions: YAML 1.2, literal-block multiline strings,
None-key elision).
"""

from collections.abc import Mapping
from functools import reduce
from pathlib import Path
from typing import Any, cast

from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter

from another_mood.components.shared.file_type import FileType

type JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None

type KeyPath = tuple[str, ...]
"""A sequence of dict keys for direct path access (each element is a literal key)."""


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
        loaded: object = YAML(typ="safe").load(path.read_text(encoding="utf-8"))  # type: ignore[no-untyped-call]
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


# ── Path access ──────────────────────────────────────────────────────


def pluck(record: Mapping[str, object], key_path: str | KeyPath) -> object:
    """Read the value at ``key_path`` from ``record``.

    Accepts either a dotted string path (resolved by longest-first key
    match via :func:`split_path`) or a pre-computed :data:`KeyPath` of
    literal keys.  Raises ``KeyError`` if a string path cannot be
    fully resolved.
    """
    if isinstance(key_path, str):
        keys, remaining = split_path(record, key_path)
        if remaining:
            raise KeyError(key_path)
    else:
        keys = key_path
    value: object = record
    for k in keys:
        value = cast(Mapping[str, object], value)[k]  # type: ignore[reportUnnecessaryCast]
    return value


def split_path(record: Mapping[str, object], key_path: str) -> tuple[KeyPath, str]:
    """Walk ``record`` by longest-first key match as far as possible.

    Returns ``(keys, remaining)``: ``keys`` is the directly-applicable
    :data:`KeyPath` consumed from ``key_path``, ``remaining`` is the
    suffix where descent stopped (empty when fully resolved, equal to
    ``key_path`` when no prefix matched at the root).
    """
    keys: list[str] = []
    current: object = record
    remaining = key_path
    while remaining and isinstance(current, Mapping):
        key, value = match_key(cast(Mapping[str, object], current), remaining)  # type: ignore[reportUnnecessaryCast]
        if not key:
            break
        keys.append(key)
        remaining = remaining[len(key) + 1 :]
        current = value
    return tuple(keys), remaining


def match_key(record: Mapping[str, object], key_path: str) -> tuple[str, object]:
    """Return the longest key in ``record`` matching a prefix of ``key_path``,
    with its value.  Returns ``("", record)`` if no prefix matches.
    """
    candidate = key_path
    while candidate not in record:
        if "." not in candidate:
            return "", record
        candidate = candidate.rsplit(".", 1)[0]
    return candidate, record[candidate]


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
    # Replace, never truncate in place: in a persistent stage dir the old
    # inode may be hardlink-shared with downstream copies (write-once rule).
    path.unlink(missing_ok=True)
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
