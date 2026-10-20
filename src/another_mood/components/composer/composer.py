"""Composer — combine normalized data into views."""

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.query import Query, evaluation_order
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.json_data_model import load_model, put, save_model
from another_mood.components.shared.transfer import transfer_tree
from another_mood.components.shared.windows_reserved_name import (
    ensure_not_windows_reserved,
)


@Component(
    out_dir="out_dir",
    upstream_dirs=["contents_dir", "catalog_dir"],
)
def compose(
    contents_dir: Path,
    catalog_dir: Path,
    *,
    out_dir: Path,
) -> None:
    """Copy upstream outputs, merge into a sources namespace, evaluate views."""
    contents_out = out_dir / "contents"
    catalog_out = out_dir / "catalog"
    view_results_out = out_dir / "view-results"

    transfer_tree(contents_dir, contents_out)
    transfer_tree(catalog_dir, catalog_out)

    sources: Mapping[str, object] = load_model(contents_out, catalog_out)
    raw_views = cast(
        list[dict[str, object]],
        sources.get("__definition", {}).get("views", []),
    )

    queries = {cast(str, raw["id"]): Query.from_dict(raw) for raw in raw_views}

    view_results_out.mkdir(parents=True, exist_ok=True)
    for name in evaluation_order(queries):
        # The view name is the path the result is written at; the file
        # holds that path alone, for the downstream merge to fold in.
        path = dc.Attribute.split_id(name)
        result = queries[name].apply([sources])
        sources = put(sources, path, result)
        save_model(
            ensure_not_windows_reserved(view_results_out / f"{name}.json"),
            put({}, path, result),
        )
