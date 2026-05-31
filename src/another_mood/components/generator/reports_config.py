"""Reports config — validate and parse definition/reports.yaml for the generator.

Reads the user's `reports.yaml`, validates it against the built-in
ReportsSchema, and returns its parsed ``file_per`` list. Lives under
``generator/`` because the report config is consumed by the generator
alone; the loader is a generator-local helper rather than a pipeline
stage.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import cast

from another_mood.components.shared.json_data_model import load_model
from another_mood.components.shared.user_source.diagnostic import FileValidationError
from another_mood.components.shared.user_source.source_loader import parse_yaml
from another_mood.components.shared.user_source.validator import Validator


_REPORTS_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "reports-schema.yaml")
)


@dataclass(frozen=True)
class ReportsConfig:
    """Parsed ``definition/reports.yaml``.

    Only carries ``file_per`` for now; future additions (profiles, etc.)
    extend this dataclass so callers' signatures stay stable.
    """

    file_per: Sequence[str]

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ReportsConfig":
        """Build from an already-validated reports.yaml mapping."""
        file_per_raw = cast(Sequence[object], data.get("file_per") or ())
        return cls(file_per=tuple(str(p) for p in file_per_raw))


def load_reports_config(reports_file: Path) -> ReportsConfig:
    """Validate ``reports.yaml`` against ReportsSchema and return the parsed config.

    Reads the file once. Raises ``FileValidationError`` if validation
    produces any diagnostics.
    """
    data = parse_yaml(reports_file)
    validator = Validator(load_model(_REPORTS_SCHEMA_FILE))
    if issues := validator.validate(data):
        raise FileValidationError(
            diagnostics=[issue.at_file(reports_file) for issue in issues]
        )
    return ReportsConfig.from_dict(data)
