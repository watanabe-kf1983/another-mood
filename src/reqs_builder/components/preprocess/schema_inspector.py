"""SchemaInspector — validate user schema files against SchemaSchema.

Reads all YAML files from schema_dir, validates each against the
built-in SchemaSchema, and reports errors via BuildReport.

This stage produces no data output; its sole purpose is to gate
downstream stages via BuildReport error propagation.
"""

from collections.abc import Sequence
from importlib import resources
from pathlib import Path

from reqs_builder.components.preprocess.validator import Validator
from reqs_builder.components.shared.component import Component
from reqs_builder.components.shared.diagnostic import FileValidationError
from reqs_builder.components.shared.json_data_model import load_yamls

_SCHEMA_SCHEMA_DIR = Path(
    str(resources.files("reqs_builder.resources") / "schemas" / "schema")
)


@Component(out_dir="out_dir", input_dirs=["schema_dir"])
def inspect_schema(schema_dir: Path, *, out_dir: Path) -> None:
    """Validate all schema files in schema_dir against SchemaSchema."""
    schema_files = [f for f in sorted(schema_dir.rglob("*.yaml")) if f.is_file()]
    check_schema(schema_files)


def check_schema(schema_files: Sequence[Path]) -> None:
    """Validate schema files against SchemaSchema.

    Raises FileValidationError if any file has diagnostics.
    """
    validator = build_schema_validator()
    diagnostics = [d for f in schema_files for d in validator.validate_yaml(f)]
    if diagnostics:
        raise FileValidationError(diagnostics=diagnostics)


def build_schema_validator() -> Validator:
    """Build a Validator for user schema files (against built-in SchemaSchema)."""
    return Validator(load_yamls(_SCHEMA_SCHEMA_DIR))
