"""The sentinel for a template helper's unpassed argument.

Its own module because every helper module needs it — the md format's filters,
the data-tree ones, and the engine that registers them — and it must not pull
any of them in.
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Omitted:
    """The default of an optional filter / global argument the template did not
    pass.

    Distinct from an argument passed with an absent value, which arrives as
    ``None``: a helper defaulting to ``None`` cannot tell the two apart and so
    applies its no-argument behaviour to a data gap.

    An absent argument costs only the job that argument does, not the whole
    result, and that job decides whether the sentinel is needed:

    - it only joins the display text (``link``'s ``text``): that spot renders
      empty, whereas not passing it falls back to the label — the two differ,
      so the sentinel is needed;
    - it selects the output's shape (``code_fenced``'s ``language``,
      ``to_yaml``'s ``flow``): treated the same as not passed, so a plain
      default suffices;
    - it builds an address (``node``'s ``segs`` / ``path`` / ``fragment``,
      ``child``'s ``seg``): the reference cannot be formed, so the helper
      returns ``None`` — "render empty" is not an option here, since a
      shorter address would resolve and silently link elsewhere — and the
      sentinel is needed to tell that from not passing it.
    """


OMITTED: Final = Omitted()
