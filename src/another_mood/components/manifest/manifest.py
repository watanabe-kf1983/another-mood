"""Read and validate the project manifest (sbdb.yaml). Design: 20-app/60-sbdb-manifest."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from another_mood.components.shared.json_data_model import load_model
from another_mood.components.shared.user_error import UserError
from another_mood.components.shared.user_source.diagnostic import (
    Diagnostic,
    DiagnosticEntry,
    FileValidationError,
)
from another_mood.components.shared.user_source.source_loader import parse_yaml
from another_mood.components.shared.user_source.validator import Validator

MANIFEST_FILENAME = "sbdb.yaml"

_MANIFEST_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "manifest-schema.yaml")
)


@dataclass(frozen=True)
class Manifest:
    title: str | None = None


class ManifestError(UserError):
    """Invalid sbdb.yaml — a dedicated exception, never a build-report error."""

    def __init__(self, diagnostics: Sequence[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        details = "\n".join(d.format() for d in diagnostics)
        super().__init__(f"Invalid {MANIFEST_FILENAME}:\n{details}")

    @property
    def user_error_message(self) -> str:
        return str(self)

    @property
    def diagnostic_entries(self) -> Sequence[DiagnosticEntry]:
        return [d.to_entry() for d in self.diagnostics]


def read_manifest(project_dir: Path) -> Manifest:
    manifest_file = project_dir / MANIFEST_FILENAME
    if not manifest_file.is_file():
        return Manifest()
    data = _parse(manifest_file)
    _validate(data, manifest_file)
    title = data.get("title")
    return Manifest(title=str(title) if title is not None else None)


def _parse(manifest_file: Path) -> Mapping[str, object]:
    try:
        return parse_yaml(manifest_file)
    except FileValidationError as exc:
        raise ManifestError(list(exc.diagnostics)) from exc


def _validate(data: Mapping[str, object], manifest_file: Path) -> None:
    validator = Validator(load_model(_MANIFEST_SCHEMA_FILE))
    if issues := validator.validate(data):
        raise ManifestError([issue.at_file(manifest_file) for issue in issues])
