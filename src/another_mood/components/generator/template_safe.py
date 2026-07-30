"""The marshal contract's acceptance type and the render boundary enforcing it."""

from markupsafe import Markup

from another_mood.components.generator.data_tree import Node
from another_mood.components.generator.data_tree_filters import MissingNode
from another_mood.components.generator.inert import InertValue, ensure_inert


type TemplateSafe = InertValue | Node | Markup | MissingNode
"""The concrete types a template helper (filter / global) may return — a
whitelist the engine checks at the ``filters`` / ``globals`` boundary.  Not a
base type (safety is exact-type, non-inheritable): producers declare their own
concrete return types and never name this.
"""


_NON_INERT_TEMPLATE_SAFE = (MissingNode, Markup)


def ensure_template_safe(value: object) -> TemplateSafe:
    """Marshal a value crossing into a template — wider than
    :func:`ensure_inert`, which accepts data alone."""
    if isinstance(value, _NON_INERT_TEMPLATE_SAFE):
        return value
    else:
        return ensure_inert(value)
