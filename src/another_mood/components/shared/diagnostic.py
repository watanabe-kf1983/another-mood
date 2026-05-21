"""Diagnostic model for structured validation reporting.

Based on the Diagnostic model from Language Server Protocol Specification 3.17:
https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#diagnostic
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from logging import getLogger
from pathlib import Path

from another_mood.components.shared.component.build_report import (
    DiagnosticEntry,
    ErrorEntry,
)

_logger = getLogger(__name__)


class DiagnosticSeverity(Enum):
    """Severity level of a diagnostic."""

    error = "error"
    warning = "warning"
    information = "information"
    hint = "hint"


@dataclass(frozen=True)
class Diagnostic:
    """A file validation diagnostic with source location.

    ``file`` is ``None`` when the diagnostic has no source-file
    provenance (e.g. data was constructed in memory or re-loaded
    through a non-position-preserving path).  The format / snippet /
    to_entry methods all handle the None case by emitting a
    placeholder and skipping the snippet.
    """

    file: Path | None
    line: int | None
    column: int | None
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.error
    source: str = ""

    def format(self) -> str:
        """Format for user-facing output."""
        prefix = str(self.file.resolve()) if self.file is not None else "<unknown>"
        if self.line and self.column:
            return f"  {prefix}:{self.line}:{self.column}: {self.message}"
        if self.line:
            return f"  {prefix}:{self.line}: {self.message}"
        return f"  {prefix}: {self.message}"

    def to_entry(self) -> DiagnosticEntry:
        """Convert to the report-time DiagnosticEntry, baking in the snippet.

        ``file`` becomes an empty string on the report side when the
        Diagnostic carries no source-file association.
        """
        return DiagnosticEntry(
            file=str(self.file.resolve()) if self.file is not None else "",
            line=self.line,
            column=self.column,
            message=self.message,
            severity=self.severity.value,
            source=self.source,
            snippet=self.snippet(),
        )

    def snippet(self) -> str:
        """Code-frame snippet around (line, column).

        Best-effort: returns "" on any failure (missing file, permission error,
        bug in format_pointed) and emits a warning to stderr. Snippet enrichment
        must never break diagnostic serialization.

        Returns "" immediately when ``file`` is None (no source to read).
        """
        if self.file is None:
            return ""
        try:
            text = self.file.read_text(encoding="utf-8", errors="replace")
            # Bias context upward: for YAML/JSON, parent keys above matter
            # more than siblings below.
            return format_pointed(
                self.line, self.column, text, lines_above=3, lines_below=1
            )
        except Exception as exc:
            _logger.warning("snippet generation failed for %s: %s", self.file, exc)
            return ""


class DiagnosticReporter:
    """Append-only buffer for :class:`Diagnostic` instances.

    Producers push entries via :meth:`report`; consumers read the
    accumulated snapshot through :attr:`diagnostics`.
    """

    def __init__(self) -> None:
        self._diagnostics: list[Diagnostic] = []

    def report(self, diagnostic: Diagnostic) -> None:
        """Append a diagnostic to the buffer."""
        self._diagnostics.append(diagnostic)

    @property
    def diagnostics(self) -> Sequence[Diagnostic]:
        """Snapshot of every diagnostic buffered so far."""
        return tuple(self._diagnostics)


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
    def error_entries(self) -> Sequence[ErrorEntry]:
        """Typed errors for pipeline report propagation."""
        return [ErrorEntry(message=f"FileValidationError: {self}")]

    @property
    def diagnostic_entries(self) -> Sequence[DiagnosticEntry]:
        """Typed diagnostics for pipeline report propagation."""
        return [d.to_entry() for d in self.diagnostics]


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
