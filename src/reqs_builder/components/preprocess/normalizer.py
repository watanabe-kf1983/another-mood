"""Normalizer — parse, validate, and normalize input data.

Every source file is parsed into data, validated against the schema,
and written to the output directory.
Markdown files are converted via the built-in prose schema;
YAML files are parsed with ruamel.yaml to preserve source positions
for line-number-accurate validation errors.
"""

from collections.abc import Mapping, Sequence
from importlib import resources
from pathlib import Path

from reqs_builder.components.preprocess.prose import parse_markdown
from reqs_builder.components.preprocess.validator import Validator, parse_yaml
from reqs_builder.components.shared import yaml_dumper
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.diagnostic import Diagnostic, FileValidationError
from reqs_builder.components.shared.json_data_model import load_yamls

_BUILTIN_CONTENTS_SCHEMA_DIR = Path(
    str(resources.files("reqs_builder.resources") / "schemas" / "contents")
)


@Component(out_dir="out_dir", input_dirs=["src_dir", "upstream_dir"])
def normalize(
    src_dir: Path,
    *,
    out_dir: Path,
    upstream_dir: Path | None = None,
    schema_dir: Path,
) -> None:
    """Normalize src_dir contents into out_dir."""
    check_contents(src_dir, schema_dir)
    for src_file in _source_files(src_dir):
        rel = src_file.relative_to(src_dir)
        data = _parse(src_file, rel)
        _write(data, rel, out_dir)


def check_contents(src_dir: Path, schema_dir: Path) -> None:
    """Validate all content files against built-in + user schemas.

    Raises FileValidationError if any file has diagnostics.
    """
    validator = build_contents_validator(schema_dir)
    diagnostics: list[Diagnostic] = []
    for src_file in _source_files(src_dir):
        rel = src_file.relative_to(src_dir)
        try:
            data = _parse(src_file, rel)
        except FileValidationError as exc:
            diagnostics.extend(exc.diagnostics)
            continue
        diagnostics.extend(validator.validate(data, rel))
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)


def build_contents_validator(schema_dir: Path) -> Validator:
    """Build a Validator for content files from built-in + user schemas.

    Merges the built-in prose schema with user-defined schemas from
    schema_dir, then wraps them as JSON Schema properties so that
    each top-level key in a content file is validated against its schema.
    """
    merged = load_yamls(_BUILTIN_CONTENTS_SCHEMA_DIR, schema_dir)
    schemas = merged.get("schemas", {})
    return Validator({"type": "object", "properties": schemas})


# ── helpers ────────────────────────────────────────────────────────


def _source_files(src_dir: Path) -> Sequence[Path]:
    return [f for f in sorted(src_dir.rglob("*")) if f.is_file()]


def _parse(src: Path, rel: Path) -> Mapping[str, object]:
    """Parse a source file into data."""
    if src.suffix == ".md":
        source = src.read_text(encoding="utf-8")
        record = parse_markdown(source, str(rel.with_suffix("")))
        return {"prose": [record.to_data()]}
    return parse_yaml(src)


def _write(data: Mapping[str, object], rel: Path, out_dir: Path) -> None:
    dst = out_dir / rel.with_suffix(".yaml")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        yaml_dumper.dump(data, f)
