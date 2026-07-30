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
    """


OMITTED: Final = Omitted()
