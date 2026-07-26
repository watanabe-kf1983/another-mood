"""The marshal contract's acceptance type — what a template helper may return."""

from jinja2 import Undefined
from markupsafe import Markup

from another_mood.components.generator.data_tree import Node
from another_mood.components.generator.data_tree_filters import MissingNode
from another_mood.components.generator.inert import InertValue


type TemplateSafe = InertValue | Node | Markup | MissingNode | Undefined
"""The concrete types a template helper (filter / global) may return — a
whitelist the engine checks at the ``filters`` / ``globals`` boundary.  Not a
base type (safety is exact-type, non-inheritable): producers declare their own
concrete return types and never name this.
"""
