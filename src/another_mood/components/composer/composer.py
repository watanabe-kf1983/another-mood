"""Composer — combine normalized data into views.

Passthrough-copies normalized contents and the `__definition` namespace
(data catalog + query definitions including derived entities) to views,
then evaluates queries against contents and writes the per-query
results.
"""

import shutil
from pathlib import Path
from typing import cast

from another_mood.components.composer.query import parse_query
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
    merged = load_model(queries_out)
    raw_queries = cast(
        list[dict[str, object]],
        merged.get("__definition", {}).get("queries", []),
    )

    query_results_out.mkdir(parents=True, exist_ok=True)
    for raw in raw_queries:
        name = cast(str, raw["id"])
        sources[name] = parse_query(raw).apply([sources])
        save_model(query_results_out / f"{name}.yaml", {name: sources[name]})
