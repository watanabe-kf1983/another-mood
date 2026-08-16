"""Build-info Jinja2 global — querying one run's build info store by key."""

from collections.abc import Callable, Mapping

from another_mood.components.shared.build_info import BuildInfo


def make_build_info_globals(
    info: BuildInfo,
) -> Mapping[str, Callable[..., str | None]]:
    """The ``build_info`` global, bound to one run's store."""

    def build_info(key: object, default: str | None = None) -> str | None:
        """A key with no value behind it yields ``default``."""
        if key is None:
            return default
        return info.get(str(key), default)

    return {"build_info": build_info}
