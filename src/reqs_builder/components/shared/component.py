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


@dataclass(frozen=True)
class ComponentCall:
    """A component function with directory role metadata.

    Use bind() to create a bound call for deferred execution,
    or call directly with arguments.
    """

    fn: Callable[..., None]
    out_dir_key: str
    input_dir_keys: Sequence[str]
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
    def out_dir(self) -> Path:
        return cast(Path, self.kwargs[self.out_dir_key])

    @property
    def input_dirs(self) -> Sequence[Path]:
        return [cast(Path, self.kwargs[k]) for k in self.input_dir_keys]

    def __call__(self, *args: object, **kwargs: object) -> None:
        if args or kwargs:
            self.bind(*args, **kwargs)()
        else:
            self.fn(*self.args, **self.kwargs)


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
        component = ComponentCall(
            fn=fn,
            out_dir_key=self.out_dir,
            input_dir_keys=self.input_dirs,
        )
        if self.error_propagation:
            component = _wrap_error_propagation(component)
        if self.atomic_write:
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

    return replace(component, fn=wrapped)


def _wrap_error_propagation(component: ComponentCall) -> ComponentCall:
    """Wrap a ComponentCall with error propagation."""
    from reqs_builder.components.shared.errors import (
        error_propagation as _error_propagation,
    )

    def wrapped(*args: object, **kwargs: object) -> None:
        bound = component.bind(*args, **kwargs)
        with _error_propagation(
            bound.input_dirs, bound.out_dir, stage=bound.stage
        ) as ok:
            if ok:
                bound()

    return replace(component, fn=wrapped)
