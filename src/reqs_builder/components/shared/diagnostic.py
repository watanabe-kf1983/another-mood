"""Diagnostic model for structured validation reporting.

Based on the Diagnostic model from Language Server Protocol Specification 3.17:
https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#diagnostic
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DiagnosticSeverity(Enum):
    """Severity level of a diagnostic."""

    error = "error"
    warning = "warning"
    information = "information"
    hint = "hint"


@dataclass(frozen=True)
class Diagnostic:
    """A file validation diagnostic with source location."""

    file: Path
    line: int | None
    column: int | None
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.error
    source: str = ""

    def to_data(self) -> dict[str, object]:
        """Serialize to a plain dict for YAML output."""
        return {
            "file": str(self.file.resolve()),
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source,
        }


class FileValidationError(Exception):
    """Raised when input files contain validation errors.

    Carries structured diagnostics that can be rendered to the user.
    """

    def __init__(self, diagnostics: Sequence[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        count = len(diagnostics)
        super().__init__(f"{count} validation error{'s' if count != 1 else ''}")

    @property
    def user_error_message(self) -> str:
        """Human-readable error summary for stderr output."""
        lines = [
            f"  {d.file}:{d.line}:{d.column}: {d.message}"
            if d.line
            else f"  {d.file}: {d.message}"
            for d in self.diagnostics
        ]
        return "\n".join(lines)

    @property
    def report_data(self) -> dict[str, list[dict[str, object]]]:
        """Build report content for pipeline error propagation."""
        return {
            "errors": [{"message": f"FileValidationError: {self}"}],
            "diagnostics": [d.to_data() for d in self.diagnostics],
        }
