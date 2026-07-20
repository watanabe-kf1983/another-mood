"""Content normalizer — parse, validate, and normalize source contents.

Every source file is parsed into data, validated against the merged
schema (built-in prose schema + user schema), and normalized
(dict-to-array conversion for additionalProperties patterns).  When
the data catalog is available, FK references declared via ``x-ref``
are also checked against the actual data (data-level FK integrity).
Blob sources additionally have their bytes mirrored beside their
records; hand-written ``blob`` records are rejected (blob records
come from files only).
"""

import shutil
from collections.abc import Mapping, Sequence
from importlib import resources
from pathlib import Path
from typing import cast

from another_mood.components.preprocess.data_fk_validator import check_fk_data
from another_mood.components.preprocess.normalize_core import iter_normalized
from another_mood.components.shared import data_catalog as dc
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    DiagnosticReporter,
    FileValidationError,
)
from another_mood.components.shared.user_source.source_loader import (
    UserStr,
    is_blob_file,
)
from another_mood.components.shared.json_data_model import load_model, save_model

_BUILTIN_CONTENTS_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "content-schema.yaml")
)


@Component(
    out_dir="out_dir",
    upstream_dirs=["data_catalog_dir"],
    diagnostics="reporter",
)
def normalize_contents(
    src_dir: Path,
    *,
    schema_file: Path,
    data_catalog_dir: Path,
    out_dir: Path,
    reporter: DiagnosticReporter,
) -> None:
    """Normalize src_dir contents into out_dir and report FK warnings."""
    schema = build_contents_schema(schema_file)
    data_by_entity: dict[str, list[Mapping[str, object]]] = {}
    for src_file, data in iter_normalized(src_dir, schema):
        # Append (not replace) ``.yaml`` so foo.yaml / foo.yml / foo.md
        # never collide on the same destination.
        rel = src_file.relative_to(src_dir)
        save_model(out_dir / rel.with_name(rel.name + ".yaml"), data)
        _mirror_blob_bytes(src_file, data, out_dir / rel)
        _accumulate(data, data_by_entity)

    for diagnostic in check_fk_data(_load_catalog(data_catalog_dir), data_by_entity):
        reporter.report(diagnostic)


def build_contents_schema(
    schema_file: Path,
) -> Mapping[str, object]:
    """Build a validation/normalization schema for content files.

    Merges the built-in prose schema with the user's schema.yaml.  Both
    files are root JSON Schemas (subset); the merge happens at the
    `properties` level so that each top-level key in a content file is
    validated against the matching entry.
    """
    return load_model(_BUILTIN_CONTENTS_SCHEMA_FILE, schema_file)


def _mirror_blob_bytes(src_file: Path, data: object, dest: Path) -> None:
    if _is_blob_to_mirror(src_file, data):
        # A real copy, never a hardlink to the user's source file: a shared
        # inode would let an in-place source edit corrupt the workspace and
        # published output without firing any watcher event.
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest)


def _is_blob_to_mirror(src_file: Path, data: object) -> bool:
    if is_blob_file(src_file):
        return True
    if isinstance(data, Mapping):
        payload = cast(Mapping[str, object], data)
        records = cast(Sequence[Mapping[str, object]], payload.get("blob"))
        if records:
            # blob records come from files only: a record in a YAML source
            # has no bytes behind it (or merely duplicates the file-derived
            # record), and would otherwise surface as a raw
            # FileNotFoundError in generate.
            raise FileValidationError(
                diagnostics=[_handwritten_blob(record["id"]) for record in records]
            )
    return False


def _handwritten_blob(value: object) -> Diagnostic:
    # Same location handling as data_fk_validator._fk_violation: point at
    # the YAML position when the id carries a UserStr tag.
    location = value.location if isinstance(value, UserStr) else None
    return Diagnostic(
        file=location.file if location else None,
        line=location.line if location else None,
        column=location.column if location else None,
        message=(
            f"blob.id = {str(value)!r} is hand-written; "
            f"blob records come from files only"
        ),
        source="blob-data",
    )


def _accumulate(data: object, sink: dict[str, list[Mapping[str, object]]]) -> None:
    """Merge a per-file normalized payload into the per-entity record bag.

    Only top-level keys whose value is a list (= an entity collection
    after normalization) contribute.  Fixed-object top-levels do not
    surface as FK targets and are skipped.  Multiple files sharing a
    top-level key (e.g. prose pages contributing to ``prose``) have
    their record lists concatenated.
    """
    if not isinstance(data, Mapping):
        return
    payload = cast(Mapping[str, object], data)
    for entity_id, records in payload.items():
        if isinstance(records, list):
            sink.setdefault(entity_id, []).extend(
                cast(Sequence[Mapping[str, object]], records)
            )


def _load_catalog(data_catalog_dir: Path) -> Sequence[dc.Entity]:
    """Load merged ``__definition.entities`` as typed Entity records."""
    merged = load_model(data_catalog_dir)
    raw = cast(
        Sequence[Mapping[str, object]],
        merged.get("__definition", {}).get("entities", []),
    )
    return [dc.Entity.from_dict(e) for e in raw]
