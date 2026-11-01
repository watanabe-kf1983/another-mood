"""Tap schema — the JSON Schema of the tap document, from the catalog."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.json_data_model import load_model, save_model
from another_mood.components.tap.json_schema import document_schema

TAP_SCHEMA_NAME = "schema.json"


@Component(out_dir="out_dir", upstream_dirs=["catalog_dir"])
def tap_schema(catalog_dir: Path, *, out_dir: Path) -> None:
    """Write the JSON Schema the catalog's ``__definition.entities`` describe."""
    tree = dc.build_tree(_catalog(load_model(catalog_dir)))
    save_model(out_dir / TAP_SCHEMA_NAME, document_schema(tree))


def _catalog(document: Mapping[str, object]) -> Sequence[dc.Entity]:
    definition = cast(
        Mapping[str, Sequence[Mapping[str, object]]], document["__definition"]
    )
    return [dc.Entity.from_dict(e) for e in definition["entities"]]
