"""Composer — combine normalized data into views."""

import shutil
from pathlib import Path
from typing import cast

from another_mood.components.shared.query import Query, evaluation_order
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.json_data_model import load_model, save_model
from another_mood.components.shared.windows_reserved_name import (
    ensure_not_windows_reserved,
)


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
    """Copy upstream outputs, merge into a sources namespace, evaluate queries."""
    contents_out = out_dir / "contents"
    data_catalog_out = out_dir / "data-catalog"
    queries_out = out_dir / "queries"
    query_results_out = out_dir / "query-results"

    shutil.copytree(contents_dir, contents_out)
    shutil.copytree(data_catalog_dir, data_catalog_out)
    shutil.copytree(queries_dir, queries_out)

    sources = load_model(contents_out, data_catalog_out, queries_out)
    raw_queries = cast(
        list[dict[str, object]],
        sources.get("__definition", {}).get("queries", []),
    )

    queries = {cast(str, raw["id"]): Query.from_dict(raw) for raw in raw_queries}

    query_results_out.mkdir(parents=True, exist_ok=True)
    for name in evaluation_order(queries):
        sources[name] = queries[name].apply([sources])
        save_model(
            ensure_not_windows_reserved(query_results_out / f"{name}.yaml"),
            {name: sources[name]},
        )
