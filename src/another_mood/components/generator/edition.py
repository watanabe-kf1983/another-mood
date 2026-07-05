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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import cast

from another_mood.components.generator.data_tree import Node, nearest_ancestor
from another_mood.components.generator.url import url_escape
from another_mood.components.shared.json_data_model import load_model
from another_mood.components.shared.user_source.diagnostic import FileValidationError
from another_mood.components.shared.user_source.source_loader import parse_yaml
from another_mood.components.shared.user_source.validator import Validator


_REPORTS_SCHEMA_FILE = Path(
    str(resources.files("another_mood.resources") / "schemas" / "reports-schema.yaml")
)

# Output subdirectory name for form A's single implicit edition.
_FORM_A_EDITION_NAME = "default"

# Immutable empty default — a frozen dataclass field rejects a mutable ``{}``.
_NO_EXTRA_FILTERS: Mapping[str, Callable[..., object]] = MappingProxyType({})


@dataclass(frozen=True)
class Edition:
    """One edition kind the generator renders — its output ``name``,
    page-split ``file_per``, and the template surface (``templates_dir`` /
    ``root_template`` / ``extra_filters``) that renders it.

    ``file_per`` drives :meth:`is_split_target` / :meth:`page_path`; ``name``
    is the output subdirectory segment (``{outDir}/{name}/``), empty for the
    root-mounted meta edition and for fallback renders.  The template-surface
    fields carry defaults so those fallback constructions stay terse.
    """

    file_per: Sequence[str]
    name: str = ""
    templates_dir: Path | None = None
    root_template: str = "index.md"
    extra_filters: Mapping[str, Callable[..., object]] = _NO_EXTRA_FILTERS

    @classmethod
    def from_dict(
        cls, name: str, data: Mapping[str, object], templates_dir: Path
    ) -> "Edition":
        """Build a user edition from an already-validated mapping, stamped
        with the user ``templates_dir``."""
        file_per_raw = cast(Sequence[object], data.get("file_per") or ())
        return cls(
            name=name,
            file_per=tuple(str(p) for p in file_per_raw),
            templates_dir=templates_dir,
        )

    @property
    def dir_segment(self) -> str:
        """The output subdirectory segment — ``name`` IRI-escaped.

        Edition names are validated loosely (any non-empty, non-``__``
        string), so an unsafe name is made FS- and link-safe with the same
        per-segment escape anchor_path uses (``url_escape`` with no extra
        safe chars; see :mod:`another_mood.components.generator.data_tree`).
        The generator mounts the edition at ``{out_dir}/{dir_segment}/`` and
        the meta index links to ``{dir_segment}/``, so both stay consistent.
        ASCII-safe names (``default`` / ``web`` / ``pdf``) escape to
        themselves.
        """
        return url_escape(self.name, safe="")

    @property
    def is_system(self) -> bool:
        """Whether this is a system edition (the ``__db`` self-description) vs a
        user deliverable: user names are validated non-``__`` (ReportsSchema),
        so the ``__`` prefix cleanly separates the two.
        """
        return self.name.startswith("__")

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


def load_editions(reports_file: Path, templates_dir: Path) -> Sequence[Edition]:
    """Validate ``reports.yaml`` against ReportsSchema and return its editions.

    Reads the file once. Raises ``FileValidationError`` if validation
    produces any diagnostics.  Form A (top-level ``file_per``) returns a
    single edition named ``_FORM_A_EDITION_NAME``; form B (an ``editions:``
    map) returns one edition per entry, in declaration order.
    """
    data = parse_yaml(reports_file)
    validator = Validator(load_model(_REPORTS_SCHEMA_FILE))
    if issues := validator.validate(data):
        raise FileValidationError(
            diagnostics=[issue.at_file(reports_file) for issue in issues]
        )
    editions = data.get("editions")
    if editions is None:
        # Form A: the top-level mapping is the single implicit edition.
        return (Edition.from_dict(_FORM_A_EDITION_NAME, data, templates_dir),)
    # Form B: one edition per entry. Mapping order is the declaration order
    # (ruamel preserves it), so editions publish in the order written.
    entries = cast(Mapping[str, Mapping[str, object]], editions)
    return tuple(
        Edition.from_dict(name, entry, templates_dir) for name, entry in entries.items()
    )
