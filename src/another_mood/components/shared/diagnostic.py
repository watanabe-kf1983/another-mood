"""Diagnostic model for structured validation reporting.

Based on the Diagnostic model from Language Server Protocol Specification 3.17:
https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#diagnostic
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from logging import getLogger
from pathlib import Path

_logger = getLogger(__name__)


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

    def format(self) -> str:
        """Format for user-facing output."""
        path = self.file.resolve()
        if self.line and self.column:
            return f"  {path}:{self.line}:{self.column}: {self.message}"
        if self.line:
            return f"  {path}:{self.line}: {self.message}"
        return f"  {path}: {self.message}"

    def to_data(self) -> dict[str, object]:
        """Serialize to a plain dict for YAML output."""
        return {
            "file": str(self.file.resolve()),
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source,
            "snippet": self.snippet(),
        }

    def snippet(self) -> str:
        """Code-frame snippet around (line, column).

        Best-effort: returns "" on any failure (missing file, permission error,
        bug in format_pointed) and emits a warning to stderr. Snippet enrichment
        must never break diagnostic serialization.
        """
        try:
            text = self.file.read_text(errors="replace")
            # Bias context upward: for YAML/JSON, parent keys above matter
            # more than siblings below.
            return format_pointed(
                self.line, self.column, text, lines_above=3, lines_below=1
            )
        except Exception as exc:
            _logger.warning("snippet generation failed for %s: %s", self.file, exc)
            return ""


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
        details = [d.format() for d in self.diagnostics]
        return f"Found {self}:\n" + "\n".join(details)

    @property
    def report_data(self) -> dict[str, list[dict[str, object]]]:
        """Build report content for pipeline error propagation."""
        return {
            "errors": [{"message": f"FileValidationError: {self}"}],
            "diagnostics": [d.to_data() for d in self.diagnostics],
        }


def format_pointed(
    line: int | None,
    column: int | None,
    file_text: str,
    *,
    lines_above: int = 2,
    lines_below: int = 2,
) -> str:
    """Render a code-frame snippet pointing at (line, column).

    Example — format_pointed(line=4, column=7, file_text=...):

        2 |   post:
        3 |     fields:
      > 4 |       stauts: string
          |       ^
        5 |       count: int
        6 |       author: ref

    Returns "" when line is missing or out of range.
    """
    lines = file_text.splitlines()
    if not line or line > len(lines):
        return ""

    start = max(1, line - lines_above)
    end = min(len(lines), line + lines_below)
    gutter_width = len(str(end))

    out: list[str] = []
    for n in range(start, end + 1):
        marker = ">" if n == line else " "
        out.append(f"{marker} {n:>{gutter_width}} | {lines[n - 1]}")
        if n == line and column is not None:
            out.append(f"  {' ' * gutter_width} | {' ' * (column - 1)}^")
    return "\n".join(out)
