"""Composer — combine normalized data into views.

Passthrough-copies normalized contents to views, then evaluates
query definitions (YAML DSL) and writes additional view files.
"""

import shutil
from pathlib import Path
from typing import Any

import yaml

from reqs_builder.shared.json_data_model import load_yamls
from reqs_builder.composer.query import From, Grouped, Query, Select, SelectItem


def compose(contents_dir: Path, queries_dir: Path, out_dir: Path) -> None:
    """Copy contents as passthrough, then evaluate queries and write views."""
    shutil.copytree(contents_dir, out_dir, dirs_exist_ok=True)
    sources = load_yamls(contents_dir)

    parsed_queries = {
        name: parse_query(query_def)
        for name, query_def in load_yamls(queries_dir).items()
    }

    for name, query in parsed_queries.items():
        sources[name] = query.evaluate(sources)
        (out_dir / f"{name}.yaml").write_text(
            yaml.safe_dump(
                {name: sources[name]}, allow_unicode=True, default_flow_style=False
            )
        )


def parse_query(raw: Any) -> Query:
    """Parse a YAML-loaded dict into a typed Query object.

    This is the Any-to-typed boundary: raw YAML data comes in,
    validated Query objects come out.
    """
    from_clause = From(source=raw["from"])

    grouped = None
    if "grouped" in raw:
        grouped_raw = raw["grouped"]
        grouped = Grouped(
            by=grouped_raw["by"],
            as_name=grouped_raw.get("as", from_clause.source),
        )

    select_raw: list[dict[str, str]] = raw.get("select", [])
    select = Select(
        items=[
            SelectItem(item=entry["item"], as_name=entry.get("as", entry["item"]))
            for entry in select_raw
        ]
    )

    return Query(select=select, from_clause=from_clause, grouped=grouped)
