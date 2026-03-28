"""Component — declarative callable with explicit input/output directory metadata.

A Component wraps a plain function with metadata about which keyword arguments
are input directories and which is the output directory. This enables decorators
like error_propagation and atomic_write to operate on the metadata without
introspecting kwargs at runtime.

Usage:
    @Component(out_dir="out_dir", input_dirs=["src_dir"])
    def normalize(src_dir: Path, *, out_dir: Path) -> None: ...

    # Direct call
    normalize(src_dir=some_path, out_dir=other_path)

    # Bind for deferred execution
    call = normalize.bind(src_dir=some_path, out_dir=other_path)
    call()  # executes the function
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class ComponentCall:
    """A component function with directory role metadata.

    Use bind() to create a bound call for deferred execution,
    or call directly with arguments.
    """

    _fn: Callable[..., None]
    _out_dir_key: str
    _input_dir_keys: Sequence[str]
    _args: tuple[object, ...] = ()
    _kwargs: dict[str, object] = field(default_factory=lambda: {})

    def bind(self, *args: object, **kwargs: object) -> ComponentCall:
        """Bind arguments and return a new ComponentCall ready to execute."""
        return ComponentCall(
            _fn=self._fn,
            _args=args,
            _kwargs=dict(kwargs),
            _out_dir_key=self._out_dir_key,
            _input_dir_keys=list(self._input_dir_keys),
        )

    @property
    def out_dir(self) -> Path:
        return cast(Path, self._kwargs[self._out_dir_key])

    @property
    def input_dirs(self) -> Sequence[Path]:
        return [cast(Path, self._kwargs[k]) for k in self._input_dir_keys]

    def wrap_fn(self, fn: Callable[..., None]) -> ComponentCall:
        """Return a copy with _fn replaced. For use by decorators."""
        return ComponentCall(
            _fn=fn,
            _out_dir_key=self._out_dir_key,
            _input_dir_keys=list(self._input_dir_keys),
            _args=self._args,
            _kwargs=dict(self._kwargs),
        )

    def __call__(self, *args: object, **kwargs: object) -> None:
        if args or kwargs:
            self.bind(*args, **kwargs)()
        else:
            self._fn(*self._args, **self._kwargs)


class Component:
    """Decorator that converts a function into a ComponentCall.

    Usage:
        @Component(out_dir="out_dir", input_dirs=["src_dir"])
        def normalize(src_dir: Path, *, out_dir: Path) -> None: ...
    """

    def __init__(self, *, out_dir: str, input_dirs: Sequence[str]) -> None:
        self._out_dir_key = out_dir
        self._input_dir_keys = input_dirs

    def __call__(self, fn: Callable[..., None]) -> ComponentCall:
        return ComponentCall(
            _fn=fn,
            _out_dir_key=self._out_dir_key,
            _input_dir_keys=list(self._input_dir_keys),
        )
