"""Error data model — __errors serialization for pipeline error propagation.

See: docs-src/contents/internal/error-propagation.md
"""

import sys
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from reqs_builder.components.shared import yaml_dumper
from reqs_builder.components.shared.component import ComponentCall

_ERRORS_KEY = "__errors"


def with_error_propagation(component: ComponentCall) -> ComponentCall:
    """Decorator: wrap a ComponentCall with error propagation.

    Uses component metadata (input_dirs, out_dir) instead of
    introspecting kwargs at runtime.

    1. Check input dirs for __errors YAML; if any, passthrough and skip fn
    2. Catch fn exceptions → write __errors YAML to output
    """

    def wrapped(*args: object, **kwargs: object) -> None:
        bound = component.bind(*args, **kwargs)
        if _check_and_passthrough_errors(bound.input_dirs, bound.out_dir):
            return
        try:
            bound()
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            _write_exception(exc, bound.out_dir)

    return component.wrap_fn(wrapped)


def _check_and_passthrough_errors(input_dirs: Sequence[Path], out_dir: Path) -> bool:
    """Check input dirs for __errors and passthrough to out_dir."""
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
