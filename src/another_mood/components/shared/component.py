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
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import cast

from another_mood.components.shared.exclusive_write import exclusive_write
from another_mood.components.shared.errors import error_propagation


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
    use_exclusive_write: bool = True
    use_error_propagation: bool = True
    args: tuple[object, ...] = ()
    kwargs: dict[str, object] = field(default_factory=lambda: {})

    def bind(self, *args: object, **kwargs: object) -> ComponentCall:
        """Bind arguments and return a new ComponentCall ready to execute."""
        return replace(self, args=args, kwargs=kwargs)

    @property
    def upstream_dirs(self) -> Sequence[Path]:
        return [
            cast(Path, v)
            for k in self.upstream_dir_keys
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
                    self.upstream_dirs, out_dir, component=self.name
                ) as data_dirs:
                    if data_dirs is not None:
                        updated = {
                            **kwargs,
                            self.out_dir_key: data_dirs.out,
                        }
                        for key, path in zip(
                            self.upstream_dir_keys, data_dirs.upstreams
                        ):
                            updated[key] = path
                        _inner(*args, **updated)

            action = _with_propagation

        if self.use_exclusive_write:
            _inner2 = action

            def _with_exclusive(*args: object, **kwargs: object) -> None:
                out_dir = cast(Path, kwargs[self.out_dir_key])
                with exclusive_write(out_dir) as tmp_dir:
                    _inner2(*args, **{**kwargs, self.out_dir_key: tmp_dir})

            action = _with_exclusive

        action(*self.args, **self.kwargs)


@dataclass(frozen=True)
class Component:
    """Decorator that converts a function into a ComponentCall.

    Usage:
        @Component(out_dir="out_dir", upstream_dirs=["upstream_dir"])
        def normalize(src_dir: Path, *, out_dir: Path, upstream_dir: Path) -> None: ...
    """

    out_dir: str
    upstream_dirs: Sequence[str] = ()
    exclusive_write: bool = True
    error_propagation: bool = True

    def __call__(self, fn: Callable[..., None]) -> ComponentCall:
        return ComponentCall(
            fn=fn,
            name=fn.__name__,
            out_dir_key=self.out_dir,
            upstream_dir_keys=self.upstream_dirs,
            use_exclusive_write=self.exclusive_write,
            use_error_propagation=self.error_propagation,
        )
