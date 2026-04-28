"""Query normalizer — validate and normalize query DSL files.

Validates query files against the built-in query schema and writes
them under ``__definition.queries`` for downstream consumption by the
composer.
"""

from collections.abc import Mapping
from importlib import resources
from pathlib import Path

from another_mood.components.preprocess.normalize_core import normalize
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.json_data_model import load_model

_QUERY_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "query-schema.yaml")
)


@Component(out_dir="out_dir")
def normalize_queries(queries_dir: Path, *, out_dir: Path) -> None:
    """Validate and normalize query files from queries_dir into out_dir."""
    normalize(
        queries_dir,
        out_dir,
        build_query_schema(),
        wrapper=lambda data: {"__definition": {"queries": data}},
    )


def build_query_schema() -> Mapping[str, object]:
    """Build a validation/normalization schema for query files."""
    return load_model(_QUERY_SCHEMA_FILE)
