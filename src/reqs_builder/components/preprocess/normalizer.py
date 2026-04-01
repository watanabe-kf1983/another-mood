"""Normalizer — parse, validate, and normalize input data.

Every source file is parsed into data, validated against a schema
when a validator is provided, and written to the output directory.
Markdown files are converted via the built-in prose schema;
YAML files are parsed with ruamel.yaml to preserve source positions
for line-number-accurate validation errors.
"""

from collections.abc import Mapping
from pathlib import Path

from reqs_builder.components.preprocess.prose import parse_markdown
from reqs_builder.components.preprocess.validator import Validator, parse_yaml
from reqs_builder.components.shared import yaml_dumper
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.diagnostic import Diagnostic, FileValidationError


@Component(out_dir="out_dir", input_dirs=["src_dir"])
def normalize(
    src_dir: Path, *, out_dir: Path, validator: Validator | None = None
) -> None:
    """Normalize src_dir contents into out_dir."""
    all_diagnostics: list[Diagnostic] = []
    for src_file in sorted(src_dir.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)
        try:
            _process_file(src_file, rel, out_dir, validator)
        except FileValidationError as exc:
            all_diagnostics.extend(exc.diagnostics)
    if all_diagnostics:
        raise FileValidationError(diagnostics=all_diagnostics)


def _process_file(
    src: Path, rel: Path, out_dir: Path, validator: Validator | None
) -> None:
    """Parse, validate, and write a single file."""
    # Parse
    data = _parse(src, rel)

    # Validate
    if validator is not None:
        errors = validator.validate(data, rel)
        if errors:
            raise FileValidationError(diagnostics=list(errors))

    # Write
    dst = out_dir / rel.with_suffix(".yaml")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        yaml_dumper.dump(data, f)


def _parse(src: Path, rel: Path) -> Mapping[str, object]:
    """Parse a source file into data."""
    if src.suffix == ".md":
        source = src.read_text(encoding="utf-8")
        record = parse_markdown(source, str(rel.with_suffix("")))
        return {"prose": [record.to_data()]}
    return parse_yaml(src)
