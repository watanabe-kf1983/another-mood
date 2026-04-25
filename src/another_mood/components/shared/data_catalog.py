"""Data catalog model — output of SchemaInspector.

Composite-type references (``Attribute.entity``, ``Entity.parent_entity``)
are kept as plain string ids on both the in-memory and serialized sides,
so YAML round-tripping is straightforward: ``dataclasses.asdict`` for
write, ``Entity.from_dict`` for read.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Attribute:
    id: str
    type: str
    required: bool
    metadata: Mapping[str, object] | None = None
    validation: Mapping[str, object] | None = None
    entity: str | None = None  # referenced Entity.id (= access_path)
    item_type: str | None = None  # referenced ObjectType.id

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Attribute":
        return cls(**d)


@dataclass(frozen=True)
class ObjectType:
    id: str
    attributes: Sequence[Attribute]
    metadata: Mapping[str, object] | None = None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ObjectType":
        return cls(
            **_without(d, "attributes"),
            attributes=[Attribute.from_dict(a) for a in d["attributes"]],
        )


@dataclass(frozen=True)
class Entity:
    id: str
    item_type: ObjectType
    parent_entity: str | None = None
    builtin: bool = False

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Entity":
        return cls(
            **_without(d, "item_type"),
            item_type=ObjectType.from_dict(d["item_type"]),
        )


def _without(d: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k not in keys}
