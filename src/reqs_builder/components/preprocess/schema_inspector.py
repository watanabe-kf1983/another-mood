"""SchemaInspector — validate user schema files against SchemaSchema.

Reads all YAML files from schema_dir, validates each against the
built-in SchemaSchema, and reports errors via BuildReport.

This stage produces no data output; its sole purpose is to gate
downstream stages via BuildReport error propagation.
"""

from collections.abc import Mapping
from importlib import resources
from pathlib import Path

from reqs_builder.components.preprocess.validator import (
    build_validator,
    parse_yaml,
    validate_data,
)
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.diagnostic import Diagnostic, FileValidationError

_SCHEMA_SCHEMA_DIR = Path(
    str(resources.files("reqs_builder.resources") / "schemas" / "schema")
)


@Component(out_dir="out_dir", input_dirs=["schema_dir"])
def inspect_schema(schema_dir: Path, *, out_dir: Path) -> None:
    """Validate all schema files in schema_dir against SchemaSchema."""
    validator = build_validator(_SCHEMA_SCHEMA_DIR)
    all_diagnostics: list[Diagnostic] = []
    for src_file in sorted(schema_dir.rglob("*.yaml")):
        if not src_file.is_file():
            continue
        try:
            data: Mapping[str, object] = parse_yaml(src_file)
        except FileValidationError as exc:
            all_diagnostics.extend(exc.diagnostics)
            continue
        all_diagnostics.extend(validate_data(data, src_file, validator))
    if all_diagnostics:
        raise FileValidationError(diagnostics=all_diagnostics)
