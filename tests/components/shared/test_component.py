"""Tests for Component / ComponentCall."""

from pathlib import Path

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
    def test_out_dir(self) -> None:
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def my_fn(src_dir: Path, *, out_dir: Path) -> None: ...

        call = my_fn.bind(src_dir=Path("/in"), out_dir=Path("/out"))
        assert call.out_dir == Path("/out")

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
