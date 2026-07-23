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

SUPPORTED_SBDB_VERSIONS = frozenset({1})

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


class UnsupportedSbdbVersionError(UserError):
    """Unsupported sbdb generation — not a malformed file, so it carries no diagnostics."""

    def __init__(self, version: int, manifest_file: Path) -> None:
        self.version = version
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_SBDB_VERSIONS))
        hint = (
            "Upgrade another-mood to build this project."
            if version > max(SUPPORTED_SBDB_VERSIONS)
            else f"Migrate the project to sbdb_version {max(SUPPORTED_SBDB_VERSIONS)}."
        )
        super().__init__(
            f"{manifest_file} declares sbdb_version {version}, "
            f"but this another-mood supports sbdb_version {supported}. {hint}"
        )


def read_manifest(project_dir: Path) -> Manifest:
    manifest_file = project_dir / MANIFEST_FILENAME
    if not manifest_file.is_file():
        # Grace period: a missing manifest reads as sbdb_version 1, silently.
        return Manifest()
    data = _parse(manifest_file)
    # Gate before validation: a manifest from a future generation must fail as
    # "unsupported generation", not on whatever unknown key it happens to carry.
    _gate_version(data, manifest_file)
    _validate(data, manifest_file)
    title = data.get("title")
    return Manifest(title=str(title) if title is not None else None)


def _parse(manifest_file: Path) -> Mapping[str, object]:
    try:
        return parse_yaml(manifest_file)
    except FileValidationError as exc:
        raise ManifestError(list(exc.diagnostics)) from exc


def _gate_version(data: Mapping[str, object], manifest_file: Path) -> None:
    version = data.get("sbdb_version")
    # A missing or ill-typed version falls through to _validate, which locates it
    # in the file. bool needs screening out separately: it is an int subclass.
    if isinstance(version, bool) or not isinstance(version, int):
        return
    if version not in SUPPORTED_SBDB_VERSIONS:
        raise UnsupportedSbdbVersionError(version, manifest_file)


def _validate(data: Mapping[str, object], manifest_file: Path) -> None:
    validator = Validator(load_model(_MANIFEST_SCHEMA_FILE))
    if issues := validator.validate(data):
        raise ManifestError([issue.at_file(manifest_file) for issue in issues])
