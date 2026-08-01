"""Composer — combine normalized data into views."""

from pathlib import Path
from typing import cast

from another_mood.components.shared.query import Query, evaluation_order
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.json_data_model import load_model, save_model
from another_mood.components.shared.transfer import transfer_tree
from another_mood.components.shared.windows_reserved_name import (
    ensure_not_windows_reserved,
)


@Component(
    out_dir="out_dir",
    upstream_dirs=["contents_dir", "views_dir", "data_catalog_dir"],
)
def compose(
    contents_dir: Path,
    views_dir: Path,
    data_catalog_dir: Path,
    *,
    out_dir: Path,
) -> None:
    """Copy upstream outputs, merge into a sources namespace, evaluate views."""
    contents_out = out_dir / "contents"
    data_catalog_out = out_dir / "data-catalog"
    views_out = out_dir / "views"
    view_results_out = out_dir / "view-results"

    transfer_tree(contents_dir, contents_out)
    transfer_tree(data_catalog_dir, data_catalog_out)
    transfer_tree(views_dir, views_out)

    sources = load_model(contents_out, data_catalog_out, views_out)
    raw_views = cast(
        list[dict[str, object]],
        sources.get("__definition", {}).get("views", []),
    )

    queries = {cast(str, raw["id"]): Query.from_dict(raw) for raw in raw_views}

    view_results_out.mkdir(parents=True, exist_ok=True)
    for name in evaluation_order(queries):
        sources[name] = queries[name].apply([sources])
        save_model(
            ensure_not_windows_reserved(view_results_out / f"{name}.json"),
            {name: sources[name]},
        )
