"""Data catalog model — output of SchemaInspector.

Flat representation of entities and their fields, extracted from
user-defined schemas.  Consumed downstream by Composer / Generator
for meta-documentation (Phase 7).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogField:
    """A single field within an entity."""

    id: str
    type: str
    required: bool
    metadata: Mapping[str, object] | None = None
    validation: Mapping[str, object] | None = None


@dataclass(frozen=True)
class CatalogEntity:
    """An entity (table-like structure) with its fields."""

    id: str
    fields: Sequence[CatalogField]
    metadata: Mapping[str, object] | None = None
