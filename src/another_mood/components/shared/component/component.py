"""Component — declarative callable with explicit output/upstream directory metadata.

A Component wraps a plain function with metadata about which keyword argument
is the output directory and which are upstream (previous-stage output)
directories. Optional flags enable exclusive writes and error propagation.

Usage:
    @Component(out_dir="out_dir", upstream_dirs=["upstream_dir"])
    def normalize(src_dir: Path, *, out_dir: Path, upstream_dir: Path) -> None: ...

    # Direct call
    normalize(src_dir=some_path, out_dir=other_path, upstream_dir=other_path2)

    # Bind for deferred execution (component name derived from function name)
    call = normalize.bind(src_dir=some_path, out_dir=other_path, upstream_dir=other_path2)
    call()  # executes the function
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import cast

from another_mood.components.shared.component.dir_lock import (
    exclusive_read,
    exclusive_write,
)
from another_mood.components.shared.component.errors import error_propagation

_Action = Callable[..., None]


@dataclass(frozen=True)
class ComponentCall:
    """A component function with directory role metadata.

    Use bind() to create a bound call for deferred execution,
    or call directly with arguments.
    """

    fn: Callable[..., None]
    name: str
    out_dir_key: str
    upstream_dir_keys: Sequence[str] = ()
    diagnostics_key: str | None = None
    use_exclusive_write: bool = True
    use_error_propagation: bool = True
    args: tuple[object, ...] = ()
    kwargs: dict[str, object] = field(default_factory=lambda: {})

    def bind(self, *args: object, **kwargs: object) -> ComponentCall:
        """Bind arguments and return a new ComponentCall ready to execute."""
        return replace(self, args=args, kwargs=kwargs)

    def __call__(self, *args: object, **kwargs: object) -> None:
        if args or kwargs:
            self.bind(*args, **kwargs)()
        else:
            self._run()

    def _run(self) -> None:
        action: _Action = self.fn

        if self.use_error_propagation:
            action = _wrap_error_propagation(
                action,
                out_dir_key=self.out_dir_key,
                upstream_dir_keys=self.upstream_dir_keys,
                diagnostics_key=self.diagnostics_key,
                name=self.name,
            )

        if self.use_exclusive_write:
            action = _wrap_exclusive_write(action, out_dir_key=self.out_dir_key)

        if self.upstream_dir_keys:
            action = _wrap_exclusive_read(
                action, upstream_dir_keys=self.upstream_dir_keys
            )

        action(*self.args, **self.kwargs)


# -- Wrappers --------------------------------------------------------
# Module-level functions so they cannot capture `self`.  Each wrapper
# receives only the *configuration* it needs (key names, component name)
# and must read all runtime values from kwargs.


def _wrap_error_propagation(
    inner: _Action,
    *,
    out_dir_key: str,
    upstream_dir_keys: Sequence[str],
    diagnostics_key: str | None,
    name: str,
) -> _Action:
    def wrapper(*args: object, **kwargs: object) -> None:
        out_dir = cast(Path, kwargs[out_dir_key])
        upstream_dirs = [
            cast(Path, kwargs[k]) for k in upstream_dir_keys if k in kwargs
        ]
        with error_propagation(upstream_dirs, out_dir, component=name) as ctx:
            if ctx is not None:
                updated = {**kwargs, out_dir_key: ctx.out}
                for key, path in zip(upstream_dir_keys, ctx.upstreams):
                    updated[key] = path
                if diagnostics_key is not None:
                    updated[diagnostics_key] = ctx.reporter
                inner(*args, **updated)

    return wrapper


def _wrap_exclusive_write(inner: _Action, *, out_dir_key: str) -> _Action:
    def wrapper(*args: object, **kwargs: object) -> None:
        out_dir = cast(Path, kwargs[out_dir_key])
        with exclusive_write(out_dir) as tmp_dir:
            inner(*args, **{**kwargs, out_dir_key: tmp_dir})

    return wrapper


def _wrap_exclusive_read(
    inner: _Action, *, upstream_dir_keys: Sequence[str]
) -> _Action:
    def wrapper(*args: object, **kwargs: object) -> None:
        keys = [k for k in upstream_dir_keys if k in kwargs]
        with ExitStack() as stack:
            updated = {
                **kwargs,
                **{
                    k: stack.enter_context(exclusive_read(cast(Path, kwargs[k])))
                    for k in keys
                },
            }
            inner(*args, **updated)

    return wrapper


@dataclass(frozen=True)
class Component:
    """Decorator that converts a function into a ComponentCall.

    Usage:
        @Component(out_dir="out_dir", upstream_dirs=["upstream_dir"])
        def normalize(src_dir: Path, *, out_dir: Path, upstream_dir: Path) -> None: ...

    Setting ``diagnostics="<kwarg>"`` makes the framework inject a
    :class:`DiagnosticReporter` at that kwarg, so the body can report
    diagnostics without raising::

        @Component(out_dir="out_dir", diagnostics="reporter")
        def normalize(*, out_dir: Path, reporter: DiagnosticReporter) -> None: ...
    """

    out_dir: str
    upstream_dirs: Sequence[str] = ()
    diagnostics: str | None = None
    exclusive_write: bool = True
    error_propagation: bool = True

    def __call__(self, fn: Callable[..., None]) -> ComponentCall:
        return ComponentCall(
            fn=fn,
            name=fn.__name__,
            out_dir_key=self.out_dir,
            upstream_dir_keys=self.upstream_dirs,
            diagnostics_key=self.diagnostics,
            use_exclusive_write=self.exclusive_write,
            use_error_propagation=self.error_propagation,
        )
