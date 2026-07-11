"""Query deriver — validate query DSL files and derive view entities.

Validates query files against the built-in query schema, parses each
into a typed Query, and derives the synthesized catalog entities
(``view: true``) by composing the query's catalog transform against
the data catalog.  Output YAML carries both the queries and the
derived entities under ``__definition``.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from importlib import resources
from pathlib import Path
from typing import cast

from another_mood.components.preprocess.normalize_core import check
from another_mood.components.preprocess.query_normalizer import normalize_query
from another_mood.components.shared.user_source.source_loader import (
    UserStr,
    load_source,
)
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    FileValidationError,
)
from another_mood.components.shared.json_data_model import load_model, save_model
from another_mood.components.shared.query import (
    Query,
    QueryDeriveError,
    evaluation_order,
)

_QUERY_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "query-schema.yaml")
)

_BUILTIN_QUERIES_DIR = Path(str(resources.files("another_mood.resources") / "queries"))


@Component(out_dir="out_dir", upstream_dirs=["data_catalog_dir"])
def derive_queries(
    queries_dir: Path,
    *,
    data_catalog_dir: Path,
    out_dir: Path,
) -> None:
    """Validate query files and derive view entities into out_dir."""
    schema = build_query_schema()
    catalog_entities = _load_catalog(data_catalog_dir)
    catalog = dc.build_tree(catalog_entities)

    user_files = list(_iter_top_level(queries_dir, schema))
    builtin_files = list(_iter_top_level(_BUILTIN_QUERIES_DIR, schema))

    # Reject up front, not pooled with the derive-time errors below:
    # deriving over an ambiguous namespace is meaningless, and cross-query
    # references need each source name unique.
    _reject_source_name_conflicts(
        [cast(str, q["id"]) for _, queries in user_files for q in queries],
        frozenset(e.id for e in catalog_entities),
    )

    file_groups = [
        (queries_dir, out_dir, user_files),
        (_BUILTIN_QUERIES_DIR, out_dir / "__builtin", builtin_files),
    ]
    all_queries = {
        cast(str, raw["id"]): Query.from_dict(raw)
        for _, _, files in file_groups
        for _, queries in files
        for raw in queries
    }

    derived = _derive_all(all_queries, catalog)

    for src_dir, dst_dir, files in file_groups:
        for src_file, queries in files:
            # Append (not replace) ``.yaml`` so foo.yaml / foo.yml / foo.md
            # never collide on the same destination.
            rel = src_file.relative_to(src_dir)
            dst = dst_dir / rel.with_name(rel.name + ".yaml")
            save_model(
                dst,
                {
                    "__definition": {
                        "queries": list(queries),
                        "entities": [
                            entity
                            for raw in queries
                            for entity in derived[cast(str, raw["id"])]
                        ],
                    }
                },
            )


def build_query_schema() -> Mapping[str, object]:
    """Build a validation/normalization schema for query files."""
    return load_model(_QUERY_SCHEMA_FILE)


def _iter_top_level(
    src_dir: Path, schema: Mapping[str, object]
) -> Iterator[tuple[Path, list[Mapping[str, object]]]]:
    """Validate src_dir and yield top-level dict→list converted query
    lists, with each body canonicalized via ``normalize_query``.

    The catalog boundary stops at the top level — query body structure
    (e.g. the ``where:`` AST) is not normalized as catalog data. See
    design/normalizer/normalizer.md.
    """
    check(src_dir, schema)
    for src_file in sorted(src_dir.rglob("*")):
        if not src_file.is_file():
            continue
        data = load_source(src_file, src_dir)
        if data is None:
            continue
        yield (
            src_file,
            [
                normalize_query({"id": key, **cast(Mapping[str, object], body)})
                for key, body in data.items()
            ],
        )


def _reject_source_name_conflicts(
    names: Sequence[str], entity_ids: frozenset[str]
) -> None:
    """Raise :class:`FileValidationError` for name conflicts, each diagnostic
    positioned at the offending query name's YAML location."""
    conflicts = [
        _diagnostic_from(QueryDeriveError(message, offender=name))
        for message, name in _source_name_conflicts(names, entity_ids)
    ]
    if conflicts:
        raise FileValidationError(diagnostics=conflicts)


def _source_name_conflicts(
    names: Sequence[str], entity_ids: frozenset[str]
) -> list[tuple[str, str]]:
    """Find query names that shadow another source, as ``(message, name)``.

    Data entities and queries share one flat source namespace, so a
    reused name would silently shadow its source in the composer.  The
    ``__`` prefix is reserved for built-in sources — which is also why
    built-in query names never need this check.
    """
    conflicts: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in names:
        if name.startswith("__"):
            message = f"query name '{name}' is reserved: '__' marks built-in names"
        elif name in entity_ids:
            message = f"query name '{name}' collides with data entity '{name}'"
        elif name in seen:
            message = f"duplicate query name '{name}'"
        else:
            seen.add(name)
            continue
        conflicts.append((message, name))
    return conflicts


def _derive_all(
    queries: Mapping[str, Query], catalog: dc.Node
) -> Mapping[str, Sequence[Mapping[str, object]]]:
    """Derive every query in dependency order, returning each query's
    ``view: true`` entities keyed by name.

    Each view is fed back as a catalog source (see ``_with_source``) so a
    later query can read it by name.  Raises :class:`FileValidationError`
    if any query fails to derive.
    """
    try:
        order = evaluation_order(queries)
    except QueryDeriveError as exc:
        raise FileValidationError(diagnostics=[_diagnostic_from(exc)]) from exc

    diagnostics: list[Diagnostic] = []
    poisoned: set[str] = set()
    for name in order:
        query = queries[name]
        # ``poisoned`` only ever holds query names, so a data-entity source
        # is never in it — no need to filter source_names to queries here.
        if any(source in poisoned for source in query.source_names()):
            poisoned.add(name)
        else:
            try:
                view = query.derive(catalog)
            except QueryDeriveError as exc:
                diagnostics.append(_diagnostic_from(exc))
                poisoned.add(name)
            else:
                catalog = _with_source(catalog, name, view)
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)
    # Reaching here means every query derived, so each is now a top-level
    # source in ``catalog``; read the views back to serialize.
    return {
        name: [
            replace(e, view=True).to_dict()
            for e in dc.flatten_tree(catalog.child(name), name)
        ]
        for name in queries
    }


def _with_source(catalog: dc.Node, name: str, view: dc.Node) -> dc.Node:
    """Hang a derived view off the catalog's virtual root as a top-level
    ``object[]`` source, so a downstream ``From`` resolves it by name the
    same way it resolves a data entity (see ``data_catalog.build_tree``)."""
    return replace(
        catalog,
        children=[
            *catalog.children,
            (dc.Edge(name=name, type="object[]", required=True), view),
        ],
    )


def _diagnostic_from(exc: QueryDeriveError) -> Diagnostic:
    """Build a Diagnostic from a QueryDeriveError whose offender carries provenance.

    A non-UserStr offender means the identifier did not pass through the
    source loader (an internal bug, not user error), so the original
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
