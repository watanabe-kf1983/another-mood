"""YAML dumper — shared YAML serialization for all components.

Uses YAML 1.1 per json-data-model.md serialization spec.
Multiline strings are automatically rendered as literal block scalars (|).

Usage:
    from another_mood.components.shared.yaml_dumper import dump
    dump(data, stream)
"""

from collections.abc import Callable
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

_yaml = YAML()
_yaml.version = (1, 1)
_yaml.Representer = _LiteralStrRepresenter

dump: Callable[[object, IO[str]], None] = _yaml.dump  # type: ignore[reportUnknownMemberType]
