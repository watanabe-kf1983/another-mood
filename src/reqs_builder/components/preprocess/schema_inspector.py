"""SchemaInspector — validate user schema files against SchemaSchema.

Reads all YAML files from schema_dir, validates each against the
built-in SchemaSchema, and reports errors via BuildReport.

This stage produces no data output; its sole purpose is to gate
downstream stages via BuildReport error propagation.
"""

from collections.abc import Mapping
from importlib import resources
from pathlib import Path

from reqs_builder.components.preprocess.validator import Validator, parse_yaml
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.diagnostic import Diagnostic, FileValidationError

_SCHEMA_SCHEMA_DIR = Path(
    str(resources.files("reqs_builder.resources") / "schemas" / "schema")
)


def build_schema_validator() -> Validator:
    """Build a Validator for user schema files (against built-in SchemaSchema)."""
    return Validator(_SCHEMA_SCHEMA_DIR)


@Component(out_dir="out_dir", input_dirs=["schema_dir"])
def inspect_schema(schema_dir: Path, *, out_dir: Path) -> None:
    """Validate all schema files in schema_dir against SchemaSchema."""
    validator = build_schema_validator()
    all_diagnostics: list[Diagnostic] = []
    for src_file in sorted(schema_dir.rglob("*.yaml")):
        if not src_file.is_file():
            continue
        try:
            data: Mapping[str, object] = parse_yaml(src_file)
        except FileValidationError as exc:
            all_diagnostics.extend(exc.diagnostics)
            continue
        all_diagnostics.extend(validator.validate(data, src_file))
    if all_diagnostics:
        raise FileValidationError(diagnostics=all_diagnostics)
