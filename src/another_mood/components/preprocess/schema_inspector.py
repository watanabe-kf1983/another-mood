"""SchemaInspector — validate and extract metadata from the user schema file.

Reads `schema_file`, validates it against the built-in SchemaSchema,
extracts a data catalog (entities + fields), and writes the result to
`out_dir`.  Built-in content schemas (e.g. prose) are emitted under
`out_dir/__builtin/` so their entities also surface in meta-docs.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from importlib import resources
from pathlib import Path

from another_mood.components.preprocess.schema_tree import (
    ObjectNode,
    build_schema_tree,
    collect_entities,
)
from another_mood.components.shared.user_source.source_loader import UserStr, parse_yaml
from another_mood.components.shared.user_source.validator import Validator
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    FileValidationError,
)
from another_mood.components.shared.json_data_model import load_model, save_model
from another_mood.components.shared.query import Query


_SCHEMA_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "schema-schema.yaml")
)

_BUILTIN_CONTENTS_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "content-schema.yaml")
)


@Component(out_dir="out_dir")
def inspect_schema(schema_file: Path, *, out_dir: Path) -> None:
    """Validate the user schema file and extract a data catalog."""
    check_schema(schema_file)

    user_entities = _extract_from_file(schema_file)
    prose_entities = _extract_from_file(_BUILTIN_CONTENTS_SCHEMA_FILE, builtin=True)

    # __definition.* (emitted below) is intentionally not in valid_targets:
    # references to catalog metadata are not a meaningful FK relation.
    diagnostics = check_xref_coherence(
        user_entities,
        valid_targets=[*user_entities, *prose_entities],
    )
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)

    _write_catalog(user_entities, out_dir / schema_file.name)
    _write_catalog(
        prose_entities, out_dir / "__builtin" / _BUILTIN_CONTENTS_SCHEMA_FILE.name
    )

    # Emit the self-description catalog so queries can read the catalog
    # itself (e.g. ``from: __definition.entities``).  Data and schema
    # coincide here: each persisted Entity record describes one Entity.
    _emit_definition_catalog(out_dir / "__builtin" / "__definition.yaml")


def _extract_from_file(
    schema_file: Path, *, builtin: bool = False
) -> Sequence[dc.Entity]:
    schema = parse_yaml(schema_file)
    return extract_entities(schema, builtin=builtin)


def _write_catalog(entities: Sequence[dc.Entity], dst: Path) -> None:
    if entities:
        catalog = {"entities": [e.to_dict() for e in entities]}
        save_model(dst, {"__definition": catalog})


def _emit_definition_catalog(dst: Path) -> None:
    """Emit the self-description catalog for the ``__definition`` namespace.

    The entries are constructed in Python from the dataclasses' own
    ``catalog()`` methods (rather than read from a JSON Schema source
    like ``content-schema.yaml``), because no authoritative external
    schema exists for the catalog dataclasses themselves.
    """
    entities = [
        *dc.flatten_tree(dc.Entity.catalog, "__definition.entities"),
        *dc.flatten_tree(Query.catalog, "__definition.queries"),
    ]
    entities = [replace(e, builtin=True) for e in entities]
    save_model(
        dst,
        {"__definition": {"entities": [e.to_dict() for e in entities]}},
    )


def check_schema(schema_file: Path) -> None:
    """Validate the user schema file against SchemaSchema.

    Raises FileValidationError if the file has diagnostics.
    """
    if not schema_file.is_file():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    validator = build_schema_validator()
    data = parse_yaml(schema_file)
    diagnostics = [issue.at_file(schema_file) for issue in validator.validate(data)]
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)


def extract_entities(
    schema: Mapping[str, object], *, builtin: bool = False
) -> Sequence[dc.Entity]:
    """Convert a root schema into a flat list of Entity."""
    root = build_schema_tree(schema)
    if not isinstance(root, ObjectNode):
        raise ValueError(
            f"Root schema must be an object with properties; got {type(root).__name__}"
        )
    entities = collect_entities(root)
    return [replace(e, builtin=True) for e in entities] if builtin else entities


def build_schema_validator() -> Validator:
    """Build a Validator for the user schema file (against built-in SchemaSchema)."""
    return Validator(load_model(_SCHEMA_SCHEMA_FILE))


def check_xref_coherence(
    entities: Sequence[dc.Entity],
    *,
    valid_targets: Sequence[dc.Entity],
) -> Sequence[Diagnostic]:
    """Diagnose x-refs whose entity/attribute target is absent from ``valid_targets``."""
    target_index: Mapping[str, frozenset[str]] = {
        e.id: frozenset(a.id for a in e.item_type.attributes)
        for e in valid_targets
        if e.parent_entity is None
    }
    return [
        diag
        for entity in entities
        for attr in entity.item_type.attributes
        if attr.x_ref is not None
        for diag in _xref_diagnostics(attr.x_ref, target_index)
    ]


def _xref_diagnostics(
    x_ref: dc.XRef,
    target_index: Mapping[str, frozenset[str]],
) -> Sequence[Diagnostic]:
    if x_ref.entity not in target_index:
        return [
            _xref_diagnostic(
                x_ref.entity,
                f"x-ref target entity '{x_ref.entity}' not found",
            )
        ]
    if x_ref.attribute not in target_index[x_ref.entity]:
        return [
            _xref_diagnostic(
                x_ref.attribute,
                f"x-ref target attribute '{x_ref.entity}.{x_ref.attribute}' not found",
            )
        ]
    return []


def _xref_diagnostic(value: str, message: str) -> Diagnostic:
    """Build a Diagnostic from a (possibly UserStr-tagged) offender.

    When the offender carries a UserStr Location (the expected path,
    since the catalog is built from parse_yaml output), the diagnostic
    points at the originating YAML line/column.  Falls back to a
    fileless diagnostic when the tag is missing, preserving the
    message so the user still sees what went wrong instead of crashing
    on a defensive RuntimeError.
    """
    if isinstance(value, UserStr):
        location = value.location
        return Diagnostic(
            file=location.file,
            line=location.line,
            column=location.column,
            message=message,
            source="x-ref",
        )
    return Diagnostic(
        file=None,
        line=None,
        column=None,
        message=message,
        source="x-ref",
    )
