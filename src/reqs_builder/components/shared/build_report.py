"""Build report — __build_report model and I/O."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from reqs_builder.components.shared import yaml_dumper
from reqs_builder.components.shared.json_data_model import deep_merge, load_yamls

_REPORT_KEY = "__build_report"
_ERRORS_KEY = "errors"
_REPORT_FILENAME = f"{_REPORT_KEY}.yaml"


# -- Models ------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentResult:
    """Outcome of a component execution."""

    component: str
    result: str
    timestamp: str

    def to_data(self) -> Mapping[str, object]:
        return {self.component: {"result": self.result, "timestamp": self.timestamp}}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- Report ------------------------------------------------------------------


class BuildReport:
    """Mutable build report backed by a plain dict."""

    def __init__(self, data: dict[str, object] | None = None) -> None:
        self._data: dict[str, object] = dict(data) if data else {}

    @staticmethod
    def collect(*directories: Path) -> "BuildReport":
        """Collect __build_report entries from input directories."""
        merged = load_yamls(*directories)
        return BuildReport(merged.get(_REPORT_KEY))

    def has_errors(self) -> bool:
        return bool(self._data.get(_ERRORS_KEY))

    def is_empty(self) -> bool:
        return not self._data

    def add_data(self, data: Mapping[str, object]) -> None:
        self._data = deep_merge(self._data, dict(data))

    def add_component_result(self, component: str, result: str) -> None:
        if component:
            self._data.update(
                ComponentResult(
                    component=component, result=result, timestamp=_now_iso()
                ).to_data()
            )

    def to_data(self) -> Mapping[str, object]:
        """Return the report content (without the __build_report wrapper)."""
        return self._data

    def write(self, out_dir: Path) -> None:
        """Write __build_report.yaml to out_dir."""
        if self.is_empty():
            return
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / _REPORT_FILENAME).open("w") as f:
            yaml_dumper.dump({_REPORT_KEY: self._data}, f)
