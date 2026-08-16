"""Build-info Jinja2 global — querying one run's build info store by key."""

from collections.abc import Callable, Mapping

from another_mood.components.shared.build_info import BuildInfo


def make_build_info_globals(
    info: BuildInfo,
) -> Mapping[str, Callable[..., str | None]]:
    """The ``build_info`` global, bound to one run's store."""

    def build_info(key: object) -> str | None:
        """An unset key yields no value rather than an error."""
        if key is None:
            return None
        return info.get(str(key))

    return {"build_info": build_info}
