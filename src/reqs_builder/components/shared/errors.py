"""Error data model — __errors serialization for pipeline error propagation."""

import sys
import traceback
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml

from reqs_builder.components.shared import yaml_dumper

_ERRORS_KEY = "__errors"


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
    """Check input dirs for __errors and merge into a single file in out_dir."""
    all_errors: list[Any] = []
    for d in input_dirs:
        if not d.exists():
            continue
        if (errors := collect_errors(d)) is not None:
            all_errors.extend(errors[_ERRORS_KEY])
    if all_errors:
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / f"{_ERRORS_KEY}.yaml").open("w") as f:
            yaml_dumper.dump({_ERRORS_KEY: all_errors}, f)
        return True
    return False


def errors_data(exc: Exception) -> dict[str, list[dict[str, object]]]:
    """Convert an exception to __errors data structure."""
    return {
        _ERRORS_KEY: [
            {
                "source": getattr(exc, "filename", None) or "",
                "lineno": getattr(exc, "lineno", None),
                "message": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
        ]
    }


def _write_exception(exc: Exception, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{_ERRORS_KEY}.yaml").open("w") as f:
        yaml_dumper.dump(errors_data(exc), f)


def collect_errors(directory: Path) -> dict[str, list[Any]] | None:
    """Collect all __errors from YAML files in a directory.

    Returns a merged ``{"__errors": [...]}`` dict, or None if no errors found.
    """
    all_errors: list[Any] = []
    for f in sorted(directory.rglob("*.yaml")):
        extracted = _extract_errors(f)
        if extracted is not None:
            all_errors.extend(extracted[_ERRORS_KEY])
    return {_ERRORS_KEY: all_errors} if all_errors else None


def _extract_errors(path: Path) -> dict[str, Any] | None:
    """Extract __errors data from a YAML file, or None if not present."""
    loaded: object = yaml.safe_load(path.read_text())
    if isinstance(loaded, dict) and _ERRORS_KEY in loaded:
        return {_ERRORS_KEY: loaded[_ERRORS_KEY]}
    return None
