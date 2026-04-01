"""Component — declarative callable with explicit input/output directory metadata.

A Component wraps a plain function with metadata about which keyword arguments
are input directories and which is the output directory. Optional flags enable
atomic writes and error propagation.

Usage:
    @Component(out_dir="out_dir", input_dirs=["src_dir"],
               atomic_write=True, error_propagation=True)
    def normalize(src_dir: Path, *, out_dir: Path) -> None: ...

    # Direct call
    normalize(src_dir=some_path, out_dir=other_path)

    # Bind for deferred execution
    call = normalize.bind(src_dir=some_path, out_dir=other_path)
    call()  # executes the function
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import cast

from reqs_builder.components.shared.atomic_write import atomic_write
from reqs_builder.components.shared.errors import error_propagation


@dataclass(frozen=True)
class ComponentCall:
    """A component function with directory role metadata.

    Use bind() to create a bound call for deferred execution,
    or call directly with arguments.
    """

    fn: Callable[..., None]
    out_dir_key: str
    input_dir_keys: Sequence[str]
    use_atomic_write: bool = True
    use_error_propagation: bool = True
    stage: str = ""
    args: tuple[object, ...] = ()
    kwargs: dict[str, object] = field(default_factory=lambda: {})

    def bind(self, *args: object, **kwargs: object) -> ComponentCall:
        """Bind arguments and return a new ComponentCall ready to execute."""
        return replace(self, args=args, kwargs=kwargs)

    def on_stage(self, stage: str) -> ComponentCall:
        """Return a copy with the given stage name."""
        return replace(self, stage=stage)

    @property
    def input_dirs(self) -> Sequence[Path]:
        return [
            cast(Path, v)
            for k in self.input_dir_keys
            if (v := self.kwargs.get(k)) is not None
        ]

    def __call__(self, *args: object, **kwargs: object) -> None:
        if args or kwargs:
            self.bind(*args, **kwargs)()
        else:
            self._run()

    def _run(self) -> None:
        def action(*args: object, **kwargs: object) -> None:
            self.fn(*args, **kwargs)

        if self.use_error_propagation:
            _inner = action

            def _with_propagation(*args: object, **kwargs: object) -> None:
                out_dir = cast(Path, kwargs[self.out_dir_key])
                with error_propagation(
                    self.input_dirs, out_dir, stage=self.stage
                ) as ok:
                    if ok:
                        _inner(*args, **kwargs)

            action = _with_propagation

        if self.use_atomic_write:
            _inner2 = action

            def _with_atomic(*args: object, **kwargs: object) -> None:
                out_dir = cast(Path, kwargs[self.out_dir_key])
                with atomic_write(out_dir) as tmp_dir:
                    _inner2(*args, **{**kwargs, self.out_dir_key: tmp_dir})

            action = _with_atomic

        action(*self.args, **self.kwargs)


@dataclass(frozen=True)
class Component:
    """Decorator that converts a function into a ComponentCall.

    Usage:
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def normalize(src_dir: Path, *, out_dir: Path) -> None: ...
    """

    out_dir: str
    input_dirs: Sequence[str]
    atomic_write: bool = True
    error_propagation: bool = True

    def __call__(self, fn: Callable[..., None]) -> ComponentCall:
        return ComponentCall(
            fn=fn,
            out_dir_key=self.out_dir,
            input_dir_keys=self.input_dirs,
            use_atomic_write=self.atomic_write,
            use_error_propagation=self.error_propagation,
        )
