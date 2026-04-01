"""Tests for Component / ComponentCall."""

from pathlib import Path
from typing import Any

import yaml


from reqs_builder.components.shared.component import Component, ComponentCall


class TestComponent:
    def test_decorator_creates_component_call(self) -> None:
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def my_fn(src_dir: Path, *, out_dir: Path) -> None: ...

        assert isinstance(my_fn, ComponentCall)

    def test_bind_returns_component_call(self) -> None:
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def my_fn(src_dir: Path, *, out_dir: Path) -> None: ...

        call = my_fn.bind(src_dir=Path("/in"), out_dir=Path("/out"))
        assert isinstance(call, ComponentCall)


class TestComponentCall:
    def test_out_dir_in_kwargs(self) -> None:
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def my_fn(src_dir: Path, *, out_dir: Path) -> None: ...

        call = my_fn.bind(src_dir=Path("/in"), out_dir=Path("/out"))
        assert call.kwargs["out_dir"] == Path("/out")

    def test_input_dirs(self) -> None:
        @Component(out_dir="out_dir", input_dirs=["contents_dir", "queries_dir"])
        def my_fn(contents_dir: Path, queries_dir: Path, *, out_dir: Path) -> None: ...

        call = my_fn.bind(
            contents_dir=Path("/a"), queries_dir=Path("/b"), out_dir=Path("/out")
        )
        assert call.input_dirs == [Path("/a"), Path("/b")]

    def test_direct_call(self, tmp_path: Path) -> None:
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def my_fn(src_dir: Path, *, out_dir: Path) -> None:
            (out_dir / "result.txt").write_text(str(src_dir))

        out = tmp_path / "out"
        out.mkdir()
        my_fn(src_dir=Path("/input"), out_dir=out)
        assert (out / "result.txt").read_text() == "/input"

    def test_bind_then_call(self, tmp_path: Path) -> None:
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def my_fn(src_dir: Path, *, out_dir: Path) -> None:
            (out_dir / "result.txt").write_text(str(src_dir))

        out = tmp_path / "out"
        out.mkdir()
        call = my_fn.bind(src_dir=Path("/input"), out_dir=out)
        call()
        assert (out / "result.txt").read_text() == "/input"

    def test_call_with_positional_args(self, tmp_path: Path) -> None:
        @Component(out_dir="out_dir", input_dirs=[])
        def my_fn(label: str, *, out_dir: Path) -> None:
            (out_dir / "result.txt").write_text(label)

        out = tmp_path / "out"
        out.mkdir()
        my_fn("hello", out_dir=out)
        assert (out / "result.txt").read_text() == "hello"


class TestAtomicWriteWrapping:
    def test_writes_to_tmp_then_syncs(self, tmp_path: Path) -> None:
        """atomic_write replaces out_dir with a tmp dir during execution."""
        actual_out_dir = None

        @Component(out_dir="out_dir", input_dirs=[], error_propagation=False)
        def my_fn(*, out_dir: Path) -> None:
            nonlocal actual_out_dir
            actual_out_dir = out_dir
            (out_dir / "result.txt").write_text("hello")

        out = tmp_path / "output"
        my_fn(out_dir=out)

        # fn received a tmp dir, not the real out_dir
        assert actual_out_dir != out
        # but result is synced to the real out_dir
        assert (out / "result.txt").read_text() == "hello"

    def test_replaces_entire_directory(self, tmp_path: Path) -> None:
        out = tmp_path / "output"

        @Component(out_dir="out_dir", input_dirs=[], error_propagation=False)
        def write(filename: str, *, out_dir: Path) -> None:
            (out_dir / filename).write_text("x")

        write("first.txt", out_dir=out)
        assert (out / "first.txt").exists()

        write("second.txt", out_dir=out)
        assert (out / "second.txt").exists()
        assert not (out / "first.txt").exists()


class TestErrorPropagationWrapping:
    def _write_yaml(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, allow_unicode=True))

    def test_skips_fn_on_upstream_errors(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        self._write_yaml(
            input_dir / "err.yaml",
            {"__build_report": {"errors": [{"message": "upstream"}]}},
        )

        called = False

        @Component(out_dir="out_dir", input_dirs=["src_dir"], atomic_write=False)
        def my_fn(*, src_dir: Path, out_dir: Path) -> None:
            nonlocal called
            called = True

        my_fn(src_dir=input_dir, out_dir=tmp_path / "output")
        assert not called

    def test_catches_exception_and_writes_errors(self, tmp_path: Path) -> None:
        input_dir = tmp_path / "input"
        self._write_yaml(input_dir / "data.yaml", {"x": 1})

        @Component(out_dir="out_dir", input_dirs=["src_dir"], atomic_write=False)
        def my_fn(*, src_dir: Path, out_dir: Path) -> None:
            raise ValueError("boom")

        out = tmp_path / "output"
        my_fn(src_dir=input_dir, out_dir=out)

        data = yaml.safe_load((out / "__build_report.yaml").read_text())
        assert "boom" in data["__build_report"]["errors"][0]["message"]
