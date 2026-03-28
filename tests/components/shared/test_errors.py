"""Tests for error propagation."""

from pathlib import Path
from typing import Any

import yaml

from reqs_builder.components.shared.component import (
    Component,
    with_error_propagation,
)
from reqs_builder.components.shared.errors import passthrough_if_errors


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True))


class TestPassthroughIfErrors:
    def test_returns_true_and_writes_errors(self, tmp_path: Path) -> None:
        src = tmp_path / "input" / "data.yaml"
        _write_yaml(src, {"__errors": [{"message": "broken"}]})
        out_dir = tmp_path / "output"

        assert passthrough_if_errors(src, tmp_path / "input", out_dir) is True

        data = yaml.safe_load((out_dir / "data.yaml").read_text())
        assert data["__errors"][0]["message"] == "broken"

    def test_returns_false_for_normal_file(self, tmp_path: Path) -> None:
        src = tmp_path / "input" / "data.yaml"
        _write_yaml(src, {"items": [1, 2]})
        out_dir = tmp_path / "output"

        assert passthrough_if_errors(src, tmp_path / "input", out_dir) is False
        assert not out_dir.exists()

    def test_extracts_only_errors_key(self, tmp_path: Path) -> None:
        src = tmp_path / "input" / "data.yaml"
        _write_yaml(src, {"__errors": [{"message": "err"}], "other": "data"})
        out_dir = tmp_path / "output"

        passthrough_if_errors(src, tmp_path / "input", out_dir)

        data = yaml.safe_load((out_dir / "data.yaml").read_text())
        assert "__errors" in data
        assert "other" not in data


class TestWithErrorPropagation:
    def test_runs_fn_when_no_errors(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        _write_yaml(input_dir / "data.yaml", {"items": [1, 2]})

        @with_error_propagation
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def component(*, src_dir: Path, out_dir: Path) -> None:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "result.yaml").write_text("ok")

        out_dir = tmp_path / "output"
        component(src_dir=input_dir, out_dir=out_dir)

        assert (out_dir / "result.yaml").read_text() == "ok"

    def test_skips_fn_on_upstream_errors(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        _write_yaml(input_dir / "err.yaml", {"__errors": [{"message": "upstream"}]})

        called = False

        @with_error_propagation
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def component(*, src_dir: Path, out_dir: Path) -> None:
            nonlocal called
            called = True

        component(src_dir=input_dir, out_dir=tmp_path / "output")
        assert not called

    def test_catches_exception(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        _write_yaml(input_dir / "data.yaml", {"x": 1})

        @with_error_propagation
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def component(*, src_dir: Path, out_dir: Path) -> None:
            raise ValueError("boom")

        out_dir = tmp_path / "output"
        component(src_dir=input_dir, out_dir=out_dir)

        data = yaml.safe_load((out_dir / "__errors.yaml").read_text())
        assert "boom" in data["__errors"][0]["message"]
