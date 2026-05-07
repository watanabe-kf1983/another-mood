"""Error propagation — context manager for pipeline error handling."""

import traceback
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from logging import getLogger
from pathlib import Path
from typing import NamedTuple

from another_mood.components.shared.component.build_report import BuildReport

_logger = getLogger(__name__)
_ERRORS_KEY = "errors"


class DataDirs(NamedTuple):
    """Data directories resolved by error_propagation."""

    out: Path
    upstreams: Sequence[Path]


@contextmanager
def error_propagation(
    upstream_dirs: Sequence[Path], out_dir: Path, *, component: str = ""
) -> Generator[DataDirs | None, None, None]:
    """Context manager: propagate errors through the pipeline.

    Receives component-level directories (e.g. tmp/<name>/) and internally
    separates data/ and reports/ subdirectories. Yields DataDirs with
    resolved data paths on success, or None if upstream errors are found.
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
        try:
            yield DataDirs(out=data_dir, upstreams=upstream_data_dirs)
        except Exception as exc:
            result = "ng"
            _print_error(exc)
            report.add_data(_error_data(exc))
        else:
            result = "ok"
    if component:
        report.add_component_result(component, result)
    report.write(report_dir)


def _error_data(exc: Exception) -> Mapping[str, object]:
    """Convert an exception to error report data."""
    report_data = getattr(exc, "report_data", None)
    if report_data is not None:
        return report_data
    return {
        _ERRORS_KEY: [
            {
                "message": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
        ]
    }


def _print_error(exc: Exception) -> None:
    """Log a stage error.

    Uses user_error_message if the exception provides one,
    otherwise falls back to the full traceback.
    """
    msg = getattr(exc, "user_error_message", None)
    if msg is not None:
        _logger.error("%s", msg)
    else:
        _logger.error("%s", traceback.format_exc())
