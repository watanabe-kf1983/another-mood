"""Build report — typed __build_report model and I/O."""

import traceback as _traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from another_mood.components.shared.json_data_model import load_model, save_model

_REPORT_KEY = "__build_report"
_STAGES_KEY = "stages"
_ERRORS_KEY = "errors"
_DIAGNOSTICS_KEY = "diagnostics"
_REPORT_FILENAME = f"{_REPORT_KEY}.yaml"


# -- Typed entries -----------------------------------------------------------


@dataclass(frozen=True)
class StageResult:
    """Outcome of one pipeline stage."""

    component: str
    result: str  # "ok" | "ng" | "skipped"
    timestamp: str

    @classmethod
    def from_data(cls, raw: Mapping[str, object]) -> "StageResult | None":
        component = raw.get("component")
        result = raw.get("result")
        timestamp = raw.get("timestamp")
        if not (
            isinstance(component, str)
            and isinstance(result, str)
            and isinstance(timestamp, str)
        ):
            return None
        return cls(component=component, result=result, timestamp=timestamp)

    def to_data(self) -> Mapping[str, object]:
        return {
            "component": self.component,
            "result": self.result,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class ErrorEntry:
    """A single pipeline error."""

    message: str
    traceback: str | None = None

    @classmethod
    def from_data(cls, raw: Mapping[str, object]) -> "ErrorEntry":
        traceback = raw.get("traceback")
        return cls(
            message=str(raw.get("message", "")),
            traceback=traceback if isinstance(traceback, str) else None,
        )

    def to_data(self) -> Mapping[str, object]:
        if self.traceback is None:
            return {"message": self.message}
        return {"message": self.message, "traceback": self.traceback}


@dataclass(frozen=True)
class DiagnosticEntry:
    """A file-scoped validation diagnostic captured at report-write time."""

    file: str
    line: int | None
    column: int | None
    message: str
    severity: str = "error"
    source: str = ""
    snippet: str = ""

    @classmethod
    def from_data(cls, raw: Mapping[str, object]) -> "DiagnosticEntry":
        line = raw.get("line")
        column = raw.get("column")
        return cls(
            file=str(raw.get("file", "")),
            line=line if isinstance(line, int) else None,
            column=column if isinstance(column, int) else None,
            message=str(raw.get("message", "")),
            severity=str(raw.get("severity", "error")),
            source=str(raw.get("source", "")),
            snippet=str(raw.get("snippet", "")),
        )

    def to_data(self) -> Mapping[str, object]:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "severity": self.severity,
            "source": self.source,
            "snippet": self.snippet,
        }


# -- Build report ------------------------------------------------------------


@dataclass(frozen=True)
class BuildReport:
    """Typed snapshot of a __build_report.

    Frozen value type. ``with_*`` methods return a new instance with the
    change applied.
    """

    stages: Sequence[StageResult] = ()
    errors: Sequence[ErrorEntry] = ()
    diagnostics: Sequence[DiagnosticEntry] = ()

    @staticmethod
    def collect(*directories: Path) -> "BuildReport":
        """Read and merge __build_report entries from input directories."""
        return BuildReport.from_data(load_model(*directories).get(_REPORT_KEY))

    @classmethod
    def from_data(cls, data: object) -> "BuildReport":
        """Parse the dict (as read from YAML) into a typed BuildReport."""
        if not isinstance(data, Mapping):
            return cls()
        raw = cast(Mapping[str, object], data)
        return cls(
            stages=_parse_list(raw.get(_STAGES_KEY), StageResult.from_data),
            errors=_parse_list(raw.get(_ERRORS_KEY), ErrorEntry.from_data),
            diagnostics=_parse_list(
                raw.get(_DIAGNOSTICS_KEY), DiagnosticEntry.from_data
            ),
        )

    def has_errors(self) -> bool:
        return bool(self.errors)

    def is_empty(self) -> bool:
        return not (self.stages or self.errors or self.diagnostics)

    def with_added_stage(self, component: str, result: str) -> "BuildReport":
        if not component:
            return self
        new_stage = StageResult(
            component=component, result=result, timestamp=_now_iso()
        )
        return replace(self, stages=_dedupe_append(self.stages, (new_stage,)))

    def with_exception(self, exc: Exception) -> "BuildReport":
        new_errors, new_diagnostics = _entries_from_exception(exc)
        return replace(
            self,
            errors=_dedupe_append(self.errors, new_errors),
            diagnostics=_dedupe_append(self.diagnostics, new_diagnostics),
        )

    def with_added_diagnostics(
        self, diagnostics: Iterable[DiagnosticEntry]
    ) -> "BuildReport":
        """Return a copy with the given diagnostics appended (deduped)."""
        return replace(
            self,
            diagnostics=_dedupe_append(self.diagnostics, diagnostics),
        )

    def to_data(self) -> Mapping[str, object]:
        """Serialize to the dict form used by __build_report.yaml."""
        result: dict[str, object] = {}
        if self.stages:
            result[_STAGES_KEY] = [s.to_data() for s in self.stages]
        if self.errors:
            result[_ERRORS_KEY] = [e.to_data() for e in self.errors]
        if self.diagnostics:
            result[_DIAGNOSTICS_KEY] = [d.to_data() for d in self.diagnostics]
        return result

    def write(self, out_dir: Path) -> None:
        """Write __build_report.yaml to out_dir, unless empty."""
        if self.is_empty():
            return
        out_dir.mkdir(parents=True, exist_ok=True)
        save_model(out_dir / _REPORT_FILENAME, {_REPORT_KEY: self.to_data()})


# -- Helpers -----------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_list[T](
    value: object,
    parser: Callable[[Mapping[str, object]], T | None],
) -> Sequence[T]:
    """Parse a YAML-loaded list into a deduped sequence of typed entries."""
    if not isinstance(value, list):
        return ()
    out: list[T] = []
    for raw in cast(list[object], value):
        if isinstance(raw, Mapping):
            entry = parser(cast(Mapping[str, object], raw))
            if entry is not None and entry not in out:
                out.append(entry)
    return out


def _dedupe_append[T](existing: Sequence[T], new: Iterable[T]) -> Sequence[T]:
    """Concatenate while skipping items already present in ``existing``."""
    merged = list(existing)
    for item in new:
        if item not in merged:
            merged.append(item)
    return merged


def _entries_from_exception(
    exc: Exception,
) -> tuple[Sequence[ErrorEntry], Sequence[DiagnosticEntry]]:
    """Pull typed entries from an exception.

    Falls back to a single generic ErrorEntry with a Python traceback when the
    exception does not expose ``error_entries`` / ``diagnostic_entries``.
    """
    error_entries = getattr(exc, "error_entries", None)
    diagnostic_entries = getattr(exc, "diagnostic_entries", None)
    if error_entries is not None or diagnostic_entries is not None:
        return tuple(error_entries or ()), tuple(diagnostic_entries or ())
    return (
        ErrorEntry(
            message=f"{type(exc).__name__}: {exc}",
            traceback=_traceback.format_exc(),
        ),
    ), ()
