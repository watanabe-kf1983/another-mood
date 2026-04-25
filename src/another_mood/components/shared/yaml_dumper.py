"""YAML dumper — shared YAML serialization for all components.

Uses YAML 1.2 per json-data-model.md serialization spec (ruamel.yaml's
default version).  Multiline strings are automatically rendered as
literal block scalars (|).  None-valued keys are dropped recursively
before emission per the "nullable は項目自体を省略する" rule
(json-data-model.md): leaving nulls in the output makes Jinja2
templates render the string "None".

Usage:
    from another_mood.components.shared.yaml_dumper import dump
    dump(data, stream)
"""

from typing import IO, Any

from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter


class _LiteralStrRepresenter(RoundTripRepresenter):
    """Represent multiline strings as literal block scalars (|)."""

    def represent_str(self, data: str) -> object:
        if "\n" in data:
            return self.represent_scalar("tag:yaml.org,2002:str", data, style="|")  # type: ignore[reportUnknownMemberType]
        return super().represent_str(data)  # type: ignore[reportUnknownMemberType]


_LiteralStrRepresenter.add_representer(str, _LiteralStrRepresenter.represent_str)  # type: ignore[reportUnknownMemberType]


def dump(data: object, stream: IO[str]) -> None:
    """Serialize `data` as YAML 1.2 into `stream`.

    A fresh YAML instance is created per call because ruamel.yaml's
    YAML() is not thread-safe: its emitter/serializer internal state
    is shared across calls, and concurrent dumps from different
    pipeline-stage watcher threads corrupt each other's state (e.g.
    "ValueError: I/O operation on closed file").
    """
    yaml = YAML()
    yaml.Representer = _LiteralStrRepresenter
    yaml.dump(_drop_nones(data), stream)  # type: ignore[reportUnknownMemberType]


def _drop_nones(d: Any) -> Any:  # noqa: ANN401
    """Recursively drop None-valued keys from dicts in a serialized tree."""
    if isinstance(d, dict):
        return {k: _drop_nones(v) for k, v in d.items() if v is not None}  # type: ignore[reportUnknownVariableType]
    if isinstance(d, list):
        return [_drop_nones(v) for v in d]  # type: ignore[reportUnknownVariableType]
    return d
