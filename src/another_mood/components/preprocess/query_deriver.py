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

from another_mood.components.preprocess.normalize_core import iter_normalized
from another_mood.components.preprocess.source_loader import UserStr
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.diagnostic import Diagnostic, FileValidationError
from another_mood.components.shared.json_data_model import load_model, save_model
from another_mood.components.shared.query import QueryDeriveError, parse_query

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
    schema = build_query_schema()
    catalog = dc.build_tree(_load_catalog(data_catalog_dir))

    diagnostics: list[Diagnostic] = []
    pending: list[
        tuple[Path, Sequence[Mapping[str, object]], list[Mapping[str, object]]]
    ] = []
    for src_file, normalized in iter_normalized(queries_dir, schema):
        queries = cast(Sequence[Mapping[str, object]], normalized)
        entities, errors = _derive_entities(queries, catalog)
        diagnostics.extend(errors)
        pending.append((src_file, queries, entities))

    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)

    for src_file, queries, entities in pending:
        # Append (not replace) ``.yaml`` so foo.yaml / foo.yml / foo.md
        # never collide on the same destination.
        rel = src_file.relative_to(queries_dir)
        save_model(
            out_dir / rel.with_name(rel.name + ".yaml"),
            {
                "__definition": {
                    "queries": list(queries),
                    "entities": entities,
                }
            },
        )


def build_query_schema() -> Mapping[str, object]:
    """Build a validation/normalization schema for query files."""
    return load_model(_QUERY_SCHEMA_FILE)


def _derive_entities(
    queries: Sequence[Mapping[str, object]], catalog: dc.Node
) -> tuple[list[Mapping[str, object]], list[Diagnostic]]:
    """Run each query's catalog transform and flatten the result, ``view: true``.

    Identifier-mismatch errors are collected as diagnostics and skipped;
    the offending query contributes no entities.  Other queries continue.
    """
    entities: list[Mapping[str, object]] = []
    diagnostics: list[Diagnostic] = []
    for raw in queries:
        name = cast(str, raw["id"])
        try:
            derived = dc.flatten_tree(parse_query(raw).derive(catalog), name)
        except QueryDeriveError as exc:
            diagnostics.append(_diagnostic_from(exc))
            continue
        entities.extend(replace(e, view=True).to_dict() for e in derived)
    return entities, diagnostics


def _diagnostic_from(exc: QueryDeriveError) -> Diagnostic:
    """Build a Diagnostic from a QueryDeriveError whose offender carries provenance.

    A non-UserStr offender means the query data did not pass through
    ``parse_yaml`` (an internal bug, not user error), so the original
    exception is re-raised for developers to track down.
    """
    if not isinstance(exc.offender, UserStr):
        raise exc
    location = exc.offender.location
    return Diagnostic(
        file=location.file,
        line=location.line,
        column=location.column,
        message=str(exc),
        source="query_deriver",
    )


def _load_catalog(data_catalog_dir: Path) -> list[dc.Entity]:
    """Load the merged ``__definition.entities`` list as typed Entity records."""
    merged = load_model(data_catalog_dir)
    raw = cast(
        Sequence[Mapping[str, object]],
        merged.get("__definition", {}).get("entities", []),
    )
    return [dc.Entity.from_dict(e) for e in raw]
