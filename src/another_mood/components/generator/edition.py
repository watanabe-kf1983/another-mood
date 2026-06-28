# ``page_path`` reads ``node._meta`` — a template-public field under the
# reserved ``_`` prefix (see data_tree.py), not a Python-protected attr.
# pyright: reportPrivateUsage=false
"""Reports config — validate and parse definition/reports.yaml for the generator.

Reads the user's `reports.yaml`, validates it against the built-in
ReportsSchema, and returns its parsed ``file_per`` list. Lives under
``generator/`` because the report config is consumed by the generator
alone; the loader is a generator-local helper rather than a pipeline
stage.
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


@dataclass(frozen=True)
class Edition:
    """Parsed ``definition/reports.yaml``.

    Only carries ``file_per`` for now; future additions extend this
    dataclass so callers' signatures stay stable.
    """

    file_per: Sequence[str]

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Edition":
        """Build from an already-validated reports.yaml mapping."""
        file_per_raw = cast(Sequence[object], data.get("file_per") or ())
        return cls(file_per=tuple(str(p) for p in file_per_raw))

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


def load_reports_config(reports_file: Path) -> Edition:
    """Validate ``reports.yaml`` against ReportsSchema and return the parsed config.

    Reads the file once. Raises ``FileValidationError`` if validation
    produces any diagnostics.
    """
    data = parse_yaml(reports_file)
    validator = Validator(load_model(_REPORTS_SCHEMA_FILE))
    if issues := validator.validate(data):
        raise FileValidationError(
            diagnostics=[issue.at_file(reports_file) for issue in issues]
        )
    return Edition.from_dict(data)
