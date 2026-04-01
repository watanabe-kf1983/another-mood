"""SchemaInspector — validate user schema files against SchemaSchema.

Reads all YAML files from schema_dir, parses them with ruamel.yaml
(preserving source positions for line-accurate diagnostics), and
validates each against the built-in SchemaSchema.

This stage produces no data output; its sole purpose is to gate
downstream stages via BuildReport error propagation.
"""

from pathlib import Path

from ruamel.yaml import YAML  # type: ignore[attr-defined]
from ruamel.yaml import YAMLError

from reqs_builder.components.preprocess.validator import (
    build_schema_validator,
    validate_data,
)
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.diagnostic import Diagnostic, FileValidationError

_ruamel = YAML()


@Component(out_dir="out_dir", input_dirs=["schema_dir"])
def inspect_schema(schema_dir: Path, *, out_dir: Path) -> None:
    """Validate all schema files in schema_dir against SchemaSchema."""
    validator = build_schema_validator()
    all_diagnostics: list[Diagnostic] = []
    for src_file in sorted(schema_dir.rglob("*.yaml")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(schema_dir)
        try:
            data = _parse_yaml(src_file, rel)
        except FileValidationError as exc:
            all_diagnostics.extend(exc.diagnostics)
            continue
        all_diagnostics.extend(validate_data(data, rel, validator))
    if all_diagnostics:
        raise FileValidationError(diagnostics=all_diagnostics)


def _parse_yaml(src: Path, rel: Path) -> object:
    """Parse a YAML file with ruamel.yaml, preserving source positions."""
    try:
        return _ruamel.load(src.read_text(encoding="utf-8"))  # type: ignore[no-untyped-call]
    except YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        raise FileValidationError(
            diagnostics=[
                Diagnostic(
                    file=rel,
                    line=mark.line + 1 if mark else None,
                    column=mark.column + 1 if mark else None,
                    message=getattr(exc, "problem", None) or str(exc),
                    source="ruamel.yaml",
                )
            ]
        ) from exc
