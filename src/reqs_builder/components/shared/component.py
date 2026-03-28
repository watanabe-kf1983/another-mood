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
    def out_dir_key(self) -> str:
        return self._out_dir_key

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
        @Component(out_dir="out_dir", input_dirs=["src_dir"],
                   atomic_write=True, error_propagation=True)
        def normalize(src_dir: Path, *, out_dir: Path) -> None: ...
    """

    def __init__(
        self,
        *,
        out_dir: str,
        input_dirs: Sequence[str],
        atomic_write: bool = True,
        error_propagation: bool = True,
    ) -> None:
        self._out_dir_key = out_dir
        self._input_dir_keys = input_dirs
        self._atomic_write = atomic_write
        self._error_propagation = error_propagation

    def __call__(self, fn: Callable[..., None]) -> ComponentCall:
        component = ComponentCall(
            _fn=fn,
            _out_dir_key=self._out_dir_key,
            _input_dir_keys=list(self._input_dir_keys),
        )
        if self._error_propagation:
            component = _wrap_error_propagation(component)
        if self._atomic_write:
            component = _wrap_atomic_write(component)
        return component


def _wrap_atomic_write(component: ComponentCall) -> ComponentCall:
    """Wrap a ComponentCall with atomic output and ordering."""
    from reqs_builder.components.shared.atomic_write import (
        atomic_write as _atomic_write,
    )

    out_dir_key = component.out_dir_key

    def wrapped(*args: object, **kwargs: object) -> None:
        bound = component.bind(*args, **kwargs)
        with _atomic_write(bound.out_dir) as tmp_dir:
            component.bind(*args, **{**kwargs, out_dir_key: tmp_dir})()

    return component.wrap_fn(wrapped)


def _wrap_error_propagation(component: ComponentCall) -> ComponentCall:
    """Wrap a ComponentCall with error propagation."""
    from reqs_builder.components.shared.errors import (
        error_propagation as _error_propagation,
    )

    def wrapped(*args: object, **kwargs: object) -> None:
        bound = component.bind(*args, **kwargs)
        with _error_propagation(bound.input_dirs, bound.out_dir) as ok:
            if ok:
                bound()

    return component.wrap_fn(wrapped)
