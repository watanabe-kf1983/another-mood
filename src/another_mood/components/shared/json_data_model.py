"""JSON data model — load and save the project's serialized data.

Two readers, one per kind of document:

* ``load_model`` — the pipeline's stage-to-stage intermediate
  representation, serialized as JSON with ``save_model`` as its writer.
* ``load_schema`` — JSON Schema documents (the built-in schema
  resources and the user's schema file), hand-written as YAML 1.2.

Both deep-merge across multiple files / dirs.  ``save_model`` is a
single-file emit applying the project's serialization conventions:
JSON, None-key elision.
"""

import json
from collections.abc import Mapping, Sequence
from functools import reduce
from pathlib import Path
from typing import Any, cast

from ruamel.yaml import YAML

from another_mood.components.shared.file_type import FileType

type JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None

type KeyPath = tuple[str, ...]
"""A sequence of dict keys for direct path access (each element is a literal key)."""


# ── Read ─────────────────────────────────────────────────────────────


def load_model(*paths: Path) -> dict[str, Any]:
    """Load intermediate-representation files and deep-merge into one dict.

    Files are loaded in path-sorted order so the merged result is
    deterministic regardless of filesystem iteration order.
    """
    return _load_merged(FileType.JSON, paths)


def load_schema(*paths: Path) -> dict[str, Any]:
    """Load JSON Schema documents and deep-merge into a single dict.

    Schema documents are hand-written YAML: the built-in resources
    under ``resources/schemas/`` and the user's schema file.
    """
    return _load_merged(FileType.YAML, paths)


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


def _load_merged(file_type: FileType, paths: Sequence[Path]) -> dict[str, Any]:
    files = sorted(collect_files(*paths))
    return reduce(deep_merge, (_load_mapping(file_type, f) for f in files), {})


def _load_mapping(file_type: FileType, path: Path) -> dict[str, Any]:
    """Parse path as a mapping; return {} on a file-type mismatch.

    A directory can hold files of several types (blob bytes beside
    records, say), so a mismatch is skipped rather than rejected.
    """
    if file_type.match(path):
        loaded = _parse(file_type, path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(
                f"Expected a {file_type.name} mapping in {path}, "
                f"got {type(loaded).__name__}"
            )
        return loaded  # type: ignore[return-value]
    return {}


def _parse(file_type: FileType, text: str) -> object:
    """Parse text per file type into plain Python types.

    A fresh ruamel YAML instance is created per call because ``YAML()``
    is not thread-safe — its internal state is shared across calls, and
    concurrent use from different pipeline-stage watcher threads
    corrupts it.  ``typ='safe'`` returns plain Python types (dict /
    list / scalar) — round-trip mode is not needed here.
    """
    if file_type is FileType.JSON:
        return json.loads(text)
    else:
        return YAML(typ="safe").load(text)  # type: ignore[no-untyped-call]


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
    """Write `data` as JSON to `path`.

    Applies the project's serialization conventions:

    * None-valued keys are dropped recursively per the
      "nullable は項目自体を省略する" rule (json-data-model.md):
      leaving nulls in the output makes Jinja2 templates render
      the string "None".
    * ``ensure_ascii=False`` and a 2-space indent keep the file
      readable when it is inspected post-mortem.

    Values outside the JSON data model raise ``TypeError`` here; the
    pipeline is expected to have rejected them upstream.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace, never truncate in place: in a persistent stage dir the old
    # inode may be hardlink-shared with downstream copies (write-once rule).
    path.unlink(missing_ok=True)
    path.write_text(
        json.dumps(_drop_nones(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _drop_nones(d: Any) -> Any:  # noqa: ANN401
    """Recursively drop None-valued keys from dicts in a serialized tree."""
    if isinstance(d, dict):
        return {k: _drop_nones(v) for k, v in d.items() if v is not None}  # type: ignore[reportUnknownVariableType]
    if isinstance(d, list):
        return [_drop_nones(v) for v in d]  # type: ignore[reportUnknownVariableType]
    return d
