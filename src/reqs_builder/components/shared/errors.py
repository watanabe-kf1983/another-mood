"""Build report — __build_report serialization for pipeline error propagation."""

import sys
import traceback
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from functools import reduce
from pathlib import Path
from typing import Any

from reqs_builder.components.shared import yaml_dumper
from reqs_builder.components.shared.json_data_model import deep_merge, load_yamls

_REPORT_KEY = "__build_report"
_ERRORS_KEY = "errors"
_REPORT_FILENAME = f"{_REPORT_KEY}.yaml"


@contextmanager
def error_propagation(
    input_dirs: Sequence[Path], out_dir: Path
) -> Generator[bool, None, None]:
    """Context manager: propagate errors through the pipeline.

    Yields True if no input errors were found and the body should run.
    Yields False if input errors were passed through (body should be skipped).
    Catches exceptions from the body and writes __errors YAML to out_dir.
    """
    if _check_and_passthrough_errors(input_dirs, out_dir):
        yield False
        return
    try:
        yield True
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        _write_exception(exc, out_dir)


def _check_and_passthrough_errors(input_dirs: Sequence[Path], out_dir: Path) -> bool:
    """Check input dirs for __build_report and merge into a single file in out_dir."""
    report = collect_report(*input_dirs)
    if report is None or not report[_REPORT_KEY].get(_ERRORS_KEY):
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / _REPORT_FILENAME).open("w") as f:
        yaml_dumper.dump(report, f)
    return True


def _report_data(exc: Exception) -> dict[str, dict[str, list[dict[str, object]]]]:
    """Convert an exception to __build_report data structure.

    If the exception has a ``report_data`` property, use it directly.
    Otherwise, fall back to a generic error representation with traceback.
    """
    report = getattr(exc, "report_data", None)
    if report is not None:
        return {_REPORT_KEY: report}
    return {
        _REPORT_KEY: {
            _ERRORS_KEY: [
                {
                    "message": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                }
            ]
        }
    }


def _write_exception(exc: Exception, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / _REPORT_FILENAME).open("w") as f:
        yaml_dumper.dump(_report_data(exc), f)


def collect_report(*directories: Path) -> dict[str, dict[str, Any]] | None:
    """Collect all __build_report from YAML files across directories.

    Returns a merged ``{"__build_report": {"errors": [...]}}`` dict,
    or None if no report found.
    """
    merged: dict[str, Any] = reduce(
        deep_merge,
        (load_yamls(d) for d in directories if d.exists()),
        {},
    )
    if _REPORT_KEY in merged:
        return {_REPORT_KEY: merged[_REPORT_KEY]}
    return None
