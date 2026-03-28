"""Error data model — __errors serialization for pipeline error propagation.

See: docs-src/contents/internal/error-propagation.md
"""

import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import yaml

from reqs_builder.components.shared import yaml_dumper

_ERRORS_KEY = "__errors"


def with_error_propagation[**P](
    fn: Callable[P, None],
) -> Callable[P, None]:
    """Decorator: wrap a component function with error propagation.

    The decorated function must accept `out_dir` as a keyword argument.
    All other Path arguments are treated as input dirs.

    1. Copy input YAML files to out_dir; if any contain __errors, skip fn
    2. Catch fn exceptions → write __errors YAML to output
    """

    def wrapped(*args: P.args, **kwargs: P.kwargs) -> None:
        out_dir = cast(Path, kwargs["out_dir"])
        if _check_and_passthrough_errors(args, kwargs, out_dir):
            return
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            _write_exception(exc, out_dir)

    return wrapped


def _check_and_passthrough_errors(
    args: tuple[object, ...], kwargs: dict[str, object], out_dir: Path
) -> bool:
    """Collect input dirs from args/kwargs, check for __errors and passthrough."""
    input_dirs = [
        v for k, v in kwargs.items() if k != "out_dir" and isinstance(v, Path)
    ] + [a for a in args if isinstance(a, Path)]
    has_errors = False
    for d in input_dirs:
        if not d.exists():
            continue
        for f in d.rglob("*.yaml"):
            has_errors |= passthrough_if_errors(f, d, out_dir)
    return has_errors


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


def passthrough_if_errors(src: Path, base_dir: Path, out_dir: Path) -> bool:
    if (errors := _extract_errors(src)) is not None:
        dest = out_dir / src.relative_to(base_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w") as f:
            yaml_dumper.dump(errors, f)
        return True
    else:
        return False


def _extract_errors(path: Path) -> dict[str, Any] | None:
    """Extract __errors data from a YAML file, or None if not present."""
    loaded: object = yaml.safe_load(path.read_text())
    if isinstance(loaded, dict) and _ERRORS_KEY in loaded:
        return {_ERRORS_KEY: loaded[_ERRORS_KEY]}
    return None
