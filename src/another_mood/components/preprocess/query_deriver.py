"""Query deriver — validate query DSL files and derive view entities.

Validates query files against the built-in query schema, parses each
into a typed Query, and derives the synthesized catalog entities
(``view: true``) by composing the query's catalog transform against
the data catalog.  Output YAML carries both the queries and the
derived entities under ``__definition``.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from importlib import resources
from pathlib import Path
from typing import cast

from another_mood.components.composer.query import parse_query
from another_mood.components.preprocess.normalize_core import normalize
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.json_data_model import load_model

_QUERY_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "query-schema.yaml")
)


@Component(out_dir="out_dir", upstream_dirs=["data_catalog_dir"])
def derive_queries(
    queries_dir: Path,
    *,
    data_catalog_dir: Path,
    out_dir: Path,
) -> None:
    """Validate query files and derive view entities into out_dir."""
    catalog_node = dc.Node.from_flat(_load_catalog(data_catalog_dir))
    normalize(
        queries_dir,
        out_dir,
        build_query_schema(),
        wrapper=lambda data: _derive_wrapper(data, catalog_node),
    )


def build_query_schema() -> Mapping[str, object]:
    """Build a validation/normalization schema for query files."""
    return load_model(_QUERY_SCHEMA_FILE)


def _derive_wrapper(normalized: object, catalog: dc.Node) -> Mapping[str, object]:
    """Pack queries plus their derived entities under ``__definition``."""
    queries = cast(Sequence[Mapping[str, object]], normalized)
    entities: list[Mapping[str, object]] = []
    for raw in queries:
        name = cast(str, raw["id"])
        derived = parse_query(raw).derive(catalog).to_flat(name)
        entities.extend(replace(e, view=True).to_dict() for e in derived)
    return {"__definition": {"queries": list(queries), "entities": entities}}


def _load_catalog(data_catalog_dir: Path) -> list[dc.Entity]:
    """Load the merged ``__definition.entities`` list as typed Entity records."""
    merged = load_model(data_catalog_dir)
    raw = cast(
        Sequence[Mapping[str, object]],
        merged.get("__definition", {}).get("entities", []),
    )
    return [dc.Entity.from_dict(e) for e in raw]
