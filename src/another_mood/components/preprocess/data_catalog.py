"""Data catalog model — output of SchemaInspector."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Attribute:
    id: str
    type: str
    required: bool
    metadata: Mapping[str, object] | None = None
    validation: Mapping[str, object] | None = None
    entity: str | None = None  # referenced Entity.id (= access_path)
    item_type: str | None = None  # referenced ObjectType.id


@dataclass(frozen=True)
class ObjectType:
    id: str
    attributes: Sequence[Attribute]
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True)
class Entity:
    id: str
    item_type: ObjectType
    parent_entity: str | None = None
    builtin: bool = False
