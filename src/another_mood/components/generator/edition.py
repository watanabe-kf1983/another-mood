# ``page_path`` reads ``node._meta`` — a template-public field under the
# reserved ``_`` prefix (see data_tree.py), not a Python-protected attr.
# pyright: reportPrivateUsage=false
"""Edition — one report variant's output name and page-split policy.

An ``Edition`` is the unit the generator loops over: its ``name`` (the
output subdirectory segment) plus the page-split behaviour derived from
``file_per``.  :func:`load_editions` reads the user's ``reports.yaml``,
validates it against the built-in ReportsSchema, and returns the editions
it declares.  Form A (top-level ``file_per``) yields a single implicit
edition; form B (an ``editions:`` map) yields one per entry.

Lives under ``generator/`` because editions are consumed by the generator
alone; the loader is a generator-local helper rather than a pipeline stage.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import cast

from another_mood.components.generator.data_tree import Node, nearest_ancestor
from another_mood.components.shared.json_data_model import load_model
from another_mood.components.shared.user_source.diagnostic import FileValidationError
from another_mood.components.shared.user_source.source_loader import parse_yaml
from another_mood.components.shared.user_source.validator import Validator


_REPORTS_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "reports-schema.yaml")
)

# The implicit edition name for form A (top-level ``file_per``).  Kept as a
# single constant so the staged rename to ``"default"`` (the breaking output
# flip) lands in exactly one place.
_FORM_A_EDITION_NAME = "reports"


@dataclass(frozen=True)
class Edition:
    """One report edition — its output name and page-split policy.

    ``file_per`` drives :meth:`is_split_target` / :meth:`page_path`; ``name``
    is the output subdirectory segment (``{outDir}/{name}/``).  The empty
    default ``name`` is for fallback renders that write to a fixed directory
    rather than an edition mount (so ``name`` is unused there).  Future
    per-edition fields extend this dataclass so callers' signatures stay
    stable.
    """

    file_per: Sequence[str]
    name: str = ""

    @classmethod
    def from_dict(cls, name: str, data: Mapping[str, object]) -> "Edition":
        """Build from an already-validated edition mapping."""
        file_per_raw = cast(Sequence[object], data.get("file_per") or ())
        return cls(name=name, file_per=tuple(str(p) for p in file_per_raw))

    def is_split_target(self, object_type_id: str) -> bool:
        """Whether nodes of ``object_type_id`` are split into their own page.

        A node is a split target when its ``_meta.object_type_id``
        (:mod:`another_mood.components.generator.data_tree`) is listed in
        ``file_per``.  Takes the id string rather than a node since the
        membership test needs only the id.  ``file_per`` is small, so a
        linear membership test is fine.
        """
        return object_type_id in self.file_per

    def page_path(self, node: Node) -> str:
        """Report-root-relative page path the ``node`` is rendered on.

        The nearest split-target ``self``-or-ancestor's own page
        (``{anchor_path}.md``), or ``index.md`` when no ancestor is a
        split boundary (including the root).
        """
        page = nearest_ancestor(
            node, lambda n: self.is_split_target(n._meta.object_type_id)
        )
        if page is None:
            return "index.md"
        return page._meta.anchor_path.removeprefix("/") + ".md"


def load_editions(reports_file: Path) -> Sequence[Edition]:
    """Validate ``reports.yaml`` against ReportsSchema and return its editions.

    Reads the file once. Raises ``FileValidationError`` if validation
    produces any diagnostics.  Form A (top-level ``file_per``) returns a
    single edition named ``_FORM_A_EDITION_NAME``.
    """
    data = parse_yaml(reports_file)
    validator = Validator(load_model(_REPORTS_SCHEMA_FILE))
    if issues := validator.validate(data):
        raise FileValidationError(
            diagnostics=[issue.at_file(reports_file) for issue in issues]
        )
    return (Edition.from_dict(_FORM_A_EDITION_NAME, data),)
