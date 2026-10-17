"""Query deriver — validate the view files' query DSL and derive view entities.

Validates view files against the built-in view schema, parses each
view's body into a typed Query, and derives the synthesized catalog
entities (``view: true``) by composing the query's catalog transform
against the data catalog.  The output is the whole catalog: the data
catalog with the views among the root's attributes, and the views with
their derived entities, under ``__definition``.
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
from another_mood.components.shared.json_data_model import (
    collect_files,
    load_model,
    load_schema,
    save_model,
)
from another_mood.components.shared.query import (
    Query,
    QueryDeriveError,
    evaluation_order,
)

_VIEW_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "view-schema.yaml")
)

_BUILTIN_VIEWS_DIR = Path(str(resources.files("another_mood.resources") / "views"))


@Component(out_dir="out_dir", upstream_dirs=["data_catalog_dir"])
def derive_queries(
    views_dir: Path,
    *,
    data_catalog_dir: Path,
    out_dir: Path,
) -> None:
    """Validate view files and derive view entities into out_dir."""
    schema = build_view_schema()
    catalog_entities = _load_catalog(data_catalog_dir)
    catalog = dc.build_tree(catalog_entities)

    user_files = list(_iter_top_level(views_dir, schema))
    builtin_files = list(_iter_top_level(_BUILTIN_VIEWS_DIR, schema))

    # Reject up front, not pooled with the derive-time errors below:
    # deriving over an ambiguous namespace is meaningless, and cross-query
    # references need each source name unique.
    _reject_source_name_conflicts(
        [cast(str, q["id"]) for _, queries in user_files for q in queries],
        frozenset(edge.name for edge, _ in catalog.children),
    )

    file_groups = [
        (views_dir, out_dir / "views", user_files),
        (_BUILTIN_VIEWS_DIR, out_dir / "views" / "__builtin", builtin_files),
    ]
    all_queries = {
        cast(str, raw["id"]): Query.from_dict(raw)
        for _, _, files in file_groups
        for _, queries in files
        for raw in queries
    }

    view_root, *view_entities = dc.flatten_root(_derive_all(all_queries, catalog))
    _write_catalog_with_views(
        data_catalog_dir, out_dir / "data-catalog", view_root.item_type.attributes
    )

    for src_dir, dst_dir, files in file_groups:
        for src_file, queries in files:
            # Append (not replace) ``.json`` so foo.yaml / foo.yml / foo.md
            # never collide on the same destination.
            rel = src_file.relative_to(src_dir)
            dst = dst_dir / rel.with_name(rel.name + ".json")
            names = frozenset(cast(str, raw["id"]) for raw in queries)
            save_model(
                dst,
                {
                    "__definition": {
                        "views": list(queries),
                        "entities": [
                            replace(e, view=True).to_dict()
                            for e in view_entities
                            if dc.Attribute.split_id(e.id)[0] in names
                        ],
                    }
                },
            )


def build_view_schema() -> Mapping[str, object]:
    """Build a validation/normalization schema for view files."""
    return load_schema(_VIEW_SCHEMA_FILE)


def _iter_top_level(
    src_dir: Path, schema: Mapping[str, object]
) -> Iterator[tuple[Path, list[Mapping[str, object]]]]:
    """Validate src_dir and yield top-level dict→list converted view
    lists, with each view's body canonicalized via ``normalize_query``.

    The catalog boundary stops at the top level — query body structure
    (e.g. the ``where:`` AST) is not normalized as catalog data.
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
    names: Sequence[str], data_keys: frozenset[str]
) -> None:
    """Raise :class:`FileValidationError` for name conflicts, each diagnostic
    positioned at the offending view name's YAML location."""
    conflicts = [
        _diagnostic_from(QueryDeriveError(message, offender=name))
        for message, name in _source_name_conflicts(names, data_keys)
    ]
    if conflicts:
        raise FileValidationError(diagnostics=conflicts)


def _source_name_conflicts(
    names: Sequence[str], data_keys: frozenset[str]
) -> list[tuple[str, str]]:
    """Find view names that shadow another source, as ``(message, name)``.

    The data's top-level keys (``data_keys``: collections, singletons
    and scalars alike) and views share one flat source namespace, so a
    reused name would silently shadow its source in the composer.  The
    ``__`` prefix is reserved for built-in sources — which is also why
    built-in view names never need this check.
    """
    conflicts: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in names:
        if name.startswith("__"):
            message = f"view name '{name}' is reserved: '__' marks built-in names"
        elif name in data_keys:
            message = f"view name '{name}' collides with top-level data '{name}'"
        elif name in seen:
            message = f"duplicate view name '{name}'"
        else:
            seen.add(name)
            continue
        conflicts.append((message, name))
    return conflicts


def _derive_all(queries: Mapping[str, Query], catalog: dc.Node) -> dc.Node:
    """Derive every query in dependency order, returning a root holding
    each view as a branch, in ``queries`` order.

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
        if query.query_references(poisoned):
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
    # source in ``catalog``.
    return dc.Node(children=[catalog.child_entry(name) for name in queries])


def _with_source(catalog: dc.Node, name: str, view: dc.Node) -> dc.Node:
    """Hang a derived view off the catalog's root as an ``object[]``
    source, so a downstream ``From`` resolves it by name the same way it
    resolves a top-level data entity (see ``data_catalog.build_tree``)."""
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


def _write_catalog_with_views(
    src_dir: Path, dst_dir: Path, view_attributes: Sequence[dc.Attribute]
) -> None:
    """Copy the catalog files of ``src_dir`` under ``dst_dir``, appending
    ``view_attributes`` to the root entity's."""
    for src_file in sorted(collect_files(src_dir)):
        entities = cast(
            Sequence[Mapping[str, object]],
            load_model(src_file)["__definition"]["entities"],
        )
        save_model(
            dst_dir / src_file.relative_to(src_dir),
            {
                "__definition": {
                    "entities": [
                        _with_attributes(dc.Entity.from_dict(e), view_attributes)
                        if e["id"] == dc.ROOT_ENTITY_ID
                        else e
                        for e in entities
                    ]
                }
            },
        )


def _with_attributes(
    entity: dc.Entity, attributes: Sequence[dc.Attribute]
) -> Mapping[str, object]:
    item_type = entity.item_type
    return replace(
        entity,
        item_type=replace(item_type, attributes=[*item_type.attributes, *attributes]),
    ).to_dict()


def _load_catalog(data_catalog_dir: Path) -> list[dc.Entity]:
    """Load the merged ``__definition.entities`` list as typed Entity records."""
    merged = load_model(data_catalog_dir)
    raw = cast(
        Sequence[Mapping[str, object]],
        merged.get("__definition", {}).get("entities", []),
    )
    return [dc.Entity.from_dict(e) for e in raw]
