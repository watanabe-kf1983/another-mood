"""Composer — combine normalized data into views.

Passthrough-copies normalized contents and the `__definition` namespace
(data catalog + query definitions) to views, then evaluates query
definitions (YAML DSL) and writes additional view files alongside the
catalog entities those queries synthesize.
"""

import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

from another_mood.components.composer.query import (
    From,
    Grouped,
    Query,
    Select,
    SelectItem,
)
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.catalog_node import CatalogNode
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.json_data_model import load_model, save_model


@Component(
    out_dir="out_dir",
    upstream_dirs=["contents_dir", "queries_dir", "data_catalog_dir"],
)
def compose(
    contents_dir: Path,
    queries_dir: Path,
    data_catalog_dir: Path,
    *,
    out_dir: Path,
) -> None:
    """Copy contents + meta-definition passthrough, then evaluate queries."""
    contents_out = out_dir / "contents"
    data_catalog_out = out_dir / "data-catalog"
    queries_out = out_dir / "queries"
    query_results_out = out_dir / "query-results"

    shutil.copytree(contents_dir, contents_out)
    shutil.copytree(data_catalog_dir, data_catalog_out)
    shutil.copytree(queries_dir, queries_out)

    sources = load_model(contents_out)
    catalog_node = CatalogNode.build_from_catalog(_load_catalog(data_catalog_out))

    merged = load_model(queries_out)
    definition: dict[str, Any] = merged.get("__definition", {})
    raw_queries: list[dict[str, Any]] = definition.get("queries", [])
    parsed_queries = {record["id"]: parse_query(record) for record in raw_queries}

    query_results_out.mkdir(parents=True, exist_ok=True)
    for name, query in parsed_queries.items():
        sources[name] = query.apply([sources])
        synthesized = [
            replace(e, view=True)
            for e in query.derive(catalog_node).to_catalog_list(name)
        ]
        save_model(
            query_results_out / f"{name}.yaml",
            {
                "__definition": {"entities": [e.to_dict() for e in synthesized]},
                name: sources[name],
            },
        )


def _load_catalog(data_catalog_dir: Path) -> list[dc.Entity]:
    """Load the merged ``__definition.entities`` list as typed Entity records."""
    merged = load_model(data_catalog_dir)
    raw: list[dict[str, Any]] = merged.get("__definition", {}).get("entities", [])
    return [dc.Entity.from_dict(e) for e in raw]


def parse_query(raw: Any) -> Query:
    """Parse a YAML-loaded dict into a typed Query object.

    This is the Any-to-typed boundary: raw YAML data comes in,
    validated Query objects come out.
    """
    from_raw: str = raw["from"]
    from_clause = From(path=from_raw.split("."))

    grouped = None
    if "grouped" in raw:
        grouped_raw = raw["grouped"]
        grouped = Grouped(
            by=grouped_raw["by"],
            as_name=grouped_raw.get("as", from_clause.path[-1]),
        )

    select_raw: list[dict[str, str]] = raw.get("select", [])
    select = Select(
        items=[
            SelectItem(item=entry["item"], as_name=entry.get("as", entry["item"]))
            for entry in select_raw
        ]
    )

    return Query(select=select, from_clause=from_clause, grouped=grouped)
