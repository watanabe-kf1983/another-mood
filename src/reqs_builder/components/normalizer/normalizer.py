"""Normalizer — parse, validate, and normalize input data.

Every source file is parsed into data, validated against a schema
when a validator is provided, and written to the output directory.
Markdown files are converted via the built-in prose schema;
YAML files are parsed with ruamel.yaml to preserve source positions
for line-number-accurate validation errors.
"""

from pathlib import Path
from typing import Any

from jsonschema.protocols import Validator
from ruamel.yaml import YAML  # type: ignore[attr-defined]
from ruamel.yaml import YAMLError

from reqs_builder.components.normalizer.prose import parse_markdown
from reqs_builder.components.normalizer.validator import validate_data
from reqs_builder.components.shared import yaml_dumper
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.diagnostic import Diagnostic, FileValidationError

_ruamel = YAML()


@Component(out_dir="out_dir", input_dirs=["src_dir"])
def normalize(
    src_dir: Path, *, out_dir: Path, validator: Validator | None = None
) -> None:
    """Normalize src_dir contents into out_dir."""
    for src_file in sorted(src_dir.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)

        # Parse
        data, diagnostics = _parse(src_file, rel)
        if diagnostics:
            raise FileValidationError(diagnostics=list(diagnostics))

        # Validate
        if validator is not None:
            errors = validate_data(data, rel, validator)
            if errors:
                raise FileValidationError(diagnostics=list(errors))

        # Write
        dst = out_dir / rel.with_suffix(".yaml")
        dst.parent.mkdir(parents=True, exist_ok=True)
        with dst.open("w", encoding="utf-8") as f:
            yaml_dumper.dump(data, f)


def _parse(src: Path, rel: Path) -> tuple[Any, list[Diagnostic]]:
    """Parse a source file into data.

    Returns (data, diagnostics).  On parse error, data is None and
    diagnostics contains the error.
    """
    source = src.read_text(encoding="utf-8")
    if src.suffix == ".md":
        return _parse_markdown(source, rel), []
    return _parse_yaml(source, rel)


def _parse_yaml(source: str, rel: Path) -> tuple[Any, list[Diagnostic]]:
    """Parse YAML with ruamel.yaml, preserving source positions."""
    try:
        data: Any = _ruamel.load(source)  # type: ignore[no-untyped-call]
    except YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        return None, [
            Diagnostic(
                file=rel,
                line=mark.line + 1 if mark else None,
                column=mark.column + 1 if mark else None,
                message=getattr(exc, "problem", None) or str(exc),
                source="ruamel.yaml",
            )
        ]
    return data, []


def _parse_markdown(source: str, rel: Path) -> dict[str, Any]:
    record = parse_markdown(source, str(rel.with_suffix("")))
    return {"prose": [record.to_data()]}
