"""Error propagation — context manager for pipeline error handling."""

import sys
import traceback
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from reqs_builder.components.shared.build_report import BuildReport

_ERRORS_KEY = "errors"


@contextmanager
def error_propagation(
    input_dirs: Sequence[Path], out_dir: Path, *, stage: str = ""
) -> Generator[bool, None, None]:
    """Context manager: propagate errors through the pipeline.

    Collects upstream build reports, yields False if errors found.
    Otherwise yields True and runs the body. On success or failure,
    adds stage result and writes the accumulated report.
    """
    report = BuildReport.collect(*input_dirs)
    if report.has_errors():
        result = "skipped"
        yield False
    else:
        try:
            yield True
        except Exception as exc:
            result = "ng"
            _print_error(exc)
            report.add_data(_error_data(exc))
        else:
            result = "ok"
    if stage:
        print(f"{stage} {result}.", flush=True)
        report.add_stage_result(stage, result)
    report.write(out_dir)


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
    """Print error to stderr.

    Uses user_error_message if the exception provides one,
    otherwise falls back to the full traceback.
    """
    msg = getattr(exc, "user_error_message", None)
    if msg is not None:
        print(msg, file=sys.stderr)
    else:
        traceback.print_exc(file=sys.stderr)
