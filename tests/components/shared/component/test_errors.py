"""Tests for error propagation."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from another_mood.components.shared.diagnostic import Diagnostic, FileValidationError
from another_mood.components.shared.component.errors import (
    error_propagation,
)


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True))


class TestErrorPropagation:
    def test_runs_body_when_no_errors(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        _write_yaml(input_dir / "reports" / "data.yaml", {"items": [1, 2]})

        out_dir = tmp_path / "output"
        with error_propagation([input_dir], out_dir) as data_dirs:
            if data_dirs is not None:
                data_dirs.out.mkdir(parents=True, exist_ok=True)
                (data_dirs.out / "result.yaml").write_text("ok")

        assert (out_dir / "data" / "result.yaml").read_text() == "ok"

    def test_skips_body_on_upstream_errors(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        _write_yaml(
            input_dir / "reports" / "err.yaml",
            {"__build_report": {"errors": [{"message": "upstream"}]}},
        )

        ran = False
        out_dir = tmp_path / "output"
        with error_propagation([input_dir], out_dir) as data_dirs:
            if data_dirs is not None:
                ran = True

        assert not ran

    def test_catches_exception(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        _write_yaml(input_dir / "reports" / "data.yaml", {"x": 1})

        out_dir = tmp_path / "output"
        with error_propagation([input_dir], out_dir) as data_dirs:
            if data_dirs is not None:
                raise ValueError("boom")

        data = yaml.safe_load((out_dir / "reports" / "__build_report.yaml").read_text())
        assert "boom" in data["__build_report"]["errors"][0]["message"]

    def test_merges_errors_from_multiple_input_dirs(self, tmp_path: Path) -> None:
        input_a = tmp_path / "input_a"
        input_b = tmp_path / "input_b"
        _write_yaml(
            input_a / "reports" / "__build_report.yaml",
            {"__build_report": {"errors": [{"message": "err_a"}]}},
        )
        _write_yaml(
            input_b / "reports" / "__build_report.yaml",
            {"__build_report": {"errors": [{"message": "err_b"}]}},
        )

        ran = False
        out_dir = tmp_path / "output"
        with error_propagation([input_a, input_b], out_dir) as data_dirs:
            if data_dirs is not None:
                ran = True

        assert not ran
        data = yaml.safe_load((out_dir / "reports" / "__build_report.yaml").read_text())
        messages = [e["message"] for e in data["__build_report"]["errors"]]
        assert "err_a" in messages
        assert "err_b" in messages

    def test_writes_success_report_with_stage(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        _write_yaml(input_dir / "reports" / "data.yaml", {"items": [1, 2]})

        out_dir = tmp_path / "output"
        with patch(
            "another_mood.components.shared.component.build_report._now_iso",
            return_value="2026-04-01T00:00:00+00:00",
        ):
            with error_propagation(
                [input_dir], out_dir, component="normalize_contents"
            ) as data_dirs:
                if data_dirs is not None:
                    data_dirs.out.mkdir(parents=True, exist_ok=True)
                    (data_dirs.out / "result.yaml").write_text("ok")

        data = yaml.safe_load((out_dir / "reports" / "__build_report.yaml").read_text())
        assert data["__build_report"]["stages"] == [
            {
                "component": "normalize_contents",
                "result": "ok",
                "timestamp": "2026-04-01T00:00:00+00:00",
            }
        ]

    def test_writes_ng_report_with_component_on_error(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        _write_yaml(input_dir / "reports" / "data.yaml", {"x": 1})

        out_dir = tmp_path / "output"
        with patch(
            "another_mood.components.shared.component.build_report._now_iso",
            return_value="2026-04-01T00:00:00+00:00",
        ):
            with error_propagation(
                [input_dir], out_dir, component="normalize_contents"
            ) as data_dirs:
                if data_dirs is not None:
                    raise ValueError("boom")

        data = yaml.safe_load((out_dir / "reports" / "__build_report.yaml").read_text())
        assert data["__build_report"]["stages"] == [
            {
                "component": "normalize_contents",
                "result": "ng",
                "timestamp": "2026-04-01T00:00:00+00:00",
            }
        ]
        assert "boom" in data["__build_report"]["errors"][0]["message"]

    def test_catches_file_validation_error(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        _write_yaml(input_dir / "reports" / "data.yaml", {"x": 1})

        out_dir = tmp_path / "output"
        with error_propagation([input_dir], out_dir) as data_dirs:
            if data_dirs is not None:
                raise FileValidationError(
                    [
                        Diagnostic(
                            file=Path("a.yaml"), line=3, column=1, message="bad value"
                        ),
                    ]
                )

        data = yaml.safe_load((out_dir / "reports" / "__build_report.yaml").read_text())
        assert data["__build_report"] == {
            "errors": [
                {"message": "FileValidationError: 1 validation error"},
            ],
            "diagnostics": [
                {
                    "file": str(Path("a.yaml").resolve()),
                    "line": 3,
                    "column": 1,
                    "message": "bad value",
                    "severity": "error",
                    "source": "",
                    "snippet": "",
                },
            ],
        }
