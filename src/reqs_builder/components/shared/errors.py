"""Error propagation — context manager for pipeline error handling."""

import sys
import traceback
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path

from reqs_builder.components.shared.build_report import BuildReport


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
        yield False
    else:
        try:
            yield True
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            report.add_exception(exc)
            report.add_stage_failure(stage)
        else:
            report.add_stage_success(stage)
    report.write(out_dir)
