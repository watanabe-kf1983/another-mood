"""Error propagation — context manager for pipeline error handling."""

import traceback
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from logging import getLogger
from pathlib import Path
from typing import NamedTuple

from another_mood.components.shared.component.build_report import BuildReport
from another_mood.components.shared.diagnostic import DiagnosticReporter

_logger = getLogger(__name__)


class StageContext(NamedTuple):
    """Yielded by :func:`error_propagation` on success.

    ``out`` / ``upstreams`` are the data subdirectories the body reads
    and writes through.  Entries pushed to ``reporter`` are appended to
    the stage's :class:`BuildReport` after the body returns.
    """

    out: Path
    upstreams: Sequence[Path]
    reporter: DiagnosticReporter


@contextmanager
def error_propagation(
    upstream_dirs: Sequence[Path], out_dir: Path, *, component: str = ""
) -> Generator[StageContext | None, None, None]:
    """Context manager: propagate errors through the pipeline.

    Receives component-level directories (e.g. tmp/<name>/) and internally
    separates data/ and reports/ subdirectories. Yields :class:`StageContext`
    with resolved data paths and a diagnostic reporter on success, or
    ``None`` if upstream errors are found.
    """
    report_dir = out_dir / "reports"
    data_dir = out_dir / "data"
    upstream_report_dirs = [d / "reports" for d in upstream_dirs]
    upstream_data_dirs = [d / "data" for d in upstream_dirs]

    report = BuildReport.collect(*upstream_report_dirs)
    result = "skipped"
    if report.has_errors():
        yield None
    else:
        data_dir.mkdir(parents=True, exist_ok=True)
        reporter = DiagnosticReporter()
        try:
            yield StageContext(
                out=data_dir, upstreams=upstream_data_dirs, reporter=reporter
            )
        except Exception as exc:
            result = "ng"
            _log_error(exc)
            report = report.with_exception(exc)
        else:
            result = "ok"
        # Drain reported diagnostics regardless of success — warnings
        # reported before a later raise should still surface to the user.
        report = report.with_added_diagnostics(
            d.to_entry() for d in reporter.diagnostics
        )
    if component:
        report = report.with_added_stage(component, result)
    report.write(report_dir)


def _log_error(exc: Exception) -> None:
    """Log a stage error.

    Uses user_error_message if the exception provides one,
    otherwise falls back to the full traceback.
    """
    msg = getattr(exc, "user_error_message", None)
    if msg is not None:
        _logger.error("%s", msg)
    else:
        _logger.error("%s", traceback.format_exc())
