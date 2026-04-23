"""Normalizer — parse, validate, and normalize input data.

Every source file is parsed into data, validated against the schema,
and normalized (dict-to-array conversion for additionalProperties
patterns). Markdown files are converted via the built-in prose schema;
YAML files are parsed with ruamel.yaml to preserve source positions
for line-number-accurate validation errors.
"""

from collections.abc import Callable, Mapping, Sequence
from importlib import resources
from pathlib import Path
from another_mood.components.preprocess.dict_to_array import normalize_data
from another_mood.components.preprocess.prose import parse_markdown
from another_mood.components.preprocess.validator import Validator, parse_yaml
from another_mood.components.shared import yaml_dumper
from another_mood.components.shared.component import Component
from another_mood.components.shared.diagnostic import Diagnostic, FileValidationError
from another_mood.components.shared.json_data_model import load_model
from another_mood.components.shared.file_type import FileType

_BUILTIN_CONTENTS_SCHEMA_DIR = Path(
    str(resources.files("another_mood.resources") / "schemas" / "contents")
)

_QUERY_SCHEMA_DIR = Path(
    str(resources.files("another_mood.resources") / "schemas" / "queries")
)


# ── components ─────────────────────────────────────────────────────


@Component(out_dir="out_dir", upstream_dirs=["data_catalog_dir"])
def normalize_contents(
    src_dir: Path,
    *,
    schema_dir: Path,
    data_catalog_dir: Path | None = None,
    out_dir: Path,
) -> None:
    """Normalize src_dir contents into out_dir."""
    normalize(src_dir, out_dir, build_contents_schema(schema_dir))


@Component(out_dir="out_dir")
def normalize_queries(queries_dir: Path, *, out_dir: Path) -> None:
    """Validate and normalize query files from queries_dir into out_dir."""
    normalize(
        queries_dir,
        out_dir,
        build_query_schema(),
        wrapper=lambda data: {"__definition": {"queries": data}},
    )


# ── schema builders ───────────────────────────────────────────────


def build_contents_schema(
    schema_dir: Path,
) -> Mapping[str, object]:
    """Build a validation/normalization schema for content files.

    Merges the built-in prose schema with user-defined schemas from
    schema_dir, then wraps them as JSON Schema properties so that
    each top-level key in a content file is validated against its schema.
    """
    merged = load_model(_BUILTIN_CONTENTS_SCHEMA_DIR, schema_dir)
    schemas = merged.get("schemas", {})
    return {"type": "object", "properties": schemas, "additionalProperties": False}


def build_query_schema() -> Mapping[str, object]:
    """Build a validation/normalization schema for query files."""
    return load_model(_QUERY_SCHEMA_DIR)


# ── shared core ────────────────────────────────────────────────────


def normalize(
    src_dir: Path,
    out_dir: Path,
    schema: Mapping[str, object],
    *,
    wrapper: Callable[[object], object] = lambda x: x,
) -> None:
    """Validate all files, then parse, normalize, and write each to out_dir."""
    check(src_dir, schema)
    for src_file in _iter_files(src_dir):
        data = _parse(src_file, src_dir)
        if data is None:
            continue
        normalized = normalize_data(data, schema)
        _write(wrapper(normalized), src_file.relative_to(src_dir), out_dir)


def check(src_dir: Path, schema: Mapping[str, object]) -> None:
    """Validate all files in src_dir against the given schema.

    Raises FileValidationError if any file has diagnostics.
    """
    validator = Validator(schema)
    diagnostics: list[Diagnostic] = []
    for src_file in _iter_files(src_dir):
        try:
            data = _parse(src_file, src_dir)
        except FileValidationError as exc:
            diagnostics.extend(exc.diagnostics)
            continue
        if data is None:
            continue
        diagnostics.extend(validator.validate(data, src_file))
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)


# ── helpers ────────────────────────────────────────────────────────


def _iter_files(src_dir: Path) -> Sequence[Path]:
    """Recursively list regular files under src_dir (sorted)."""
    return [f for f in sorted(src_dir.rglob("*")) if f.is_file()]


def _parse(src: Path, src_dir: Path) -> Mapping[str, object] | None:
    """Parse a source file into data, or None if the file is not a recognized source."""
    if FileType.MARKDOWN.match(src):
        source = src.read_text(encoding="utf-8")
        rel = src.relative_to(src_dir)
        record = parse_markdown(source, str(rel.with_suffix("")))
        return {"prose": [record.to_data()]}
    if FileType.YAML.match(src):
        return parse_yaml(src)
    return None


def _write(data: object, rel: Path, out_dir: Path) -> None:
    # Append (not replace) so distinct source files (foo.yaml / foo.yml / foo.md)
    # never collide on the same destination.
    dst = out_dir / rel.with_name(rel.name + ".yaml")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        yaml_dumper.dump(data, f)
