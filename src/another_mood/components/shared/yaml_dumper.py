"""YAML dumper — shared YAML serialization for all components.

Uses YAML 1.1 per json-data-model.md serialization spec.
Multiline strings are automatically rendered as literal block scalars (|).

Usage:
    from another_mood.components.shared.yaml_dumper import dump
    dump(data, stream)
"""

from typing import IO

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
    """Serialize `data` as YAML 1.1 into `stream`.

    A fresh YAML instance is created per call because ruamel.yaml's
    YAML() is not thread-safe: its emitter/serializer internal state
    is shared across calls, and concurrent dumps from different
    pipeline-stage watcher threads corrupt each other's state (e.g.
    "ValueError: I/O operation on closed file").
    """
    yaml = YAML()
    yaml.version = (1, 1)
    yaml.Representer = _LiteralStrRepresenter
    yaml.dump(data, stream)  # type: ignore[reportUnknownMemberType]
