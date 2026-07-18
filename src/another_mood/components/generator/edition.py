# ``page_path`` reads ``node._meta`` — a template-public field under the
# reserved ``_`` prefix (see data_tree.py), not a Python-protected attr.
# pyright: reportPrivateUsage=false
"""Editions and their paging policy.

A :class:`PagingPolicy` is the page-split slice a render obeys — which node
types become their own page (``file_per``) and where each split page lands.
An :class:`Edition` is the full unit the generator loops over: a paging
policy plus an output ``name`` and the template surface that renders it.
:func:`load_editions` reads the user's ``reports.yaml``, validates it against
the built-in ReportsSchema, and returns the editions it declares — form A
(top-level ``file_per``) a single implicit edition, form B (an ``editions:``
map) one per entry.

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

from another_mood.components.generator.data_tree import Node, is_blob, nearest_ancestor
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
class PagingPolicy:
    """The page-split policy a render obeys: which node types split into
    their own page (``file_per``) and the anchor-derived page each node
    lands on.

    This is the slice of an edition a ``{% mood_view %}`` / link render reads
    — it decides split vs inline and where a split page goes.  Renders with
    no paging (the cover, the build-report pages) use the empty default:
    nothing splits, so everything inlines onto ``index.md``.
    """

    file_per: Sequence[str] = ()

    def is_split_target(self, object_type_id: str) -> bool:
        """Whether nodes of ``object_type_id`` split into their own page —
        their ``_meta.object_type_id``
        (:mod:`another_mood.components.generator.data_tree`) is listed in
        ``file_per``.  Takes the id string since the membership test needs
        only the id; ``file_per`` is small, so a linear test is fine.
        """
        return object_type_id in self.file_per

    def page_path(self, node: Node) -> str:
        """Report-root-relative page path the ``node`` is rendered on.

        The nearest split-target ``node``-or-ancestor's own page
        (``{anchor_path}.md``), or ``index.md`` when no ancestor is a
        split boundary (including the root).  A blob is not a rendered page
        but an output file, so its ``page`` is the blob file itself.
        """
        if is_blob(node):
            return node._meta.anchor_path.removeprefix("/")
        page = nearest_ancestor(
            node, lambda n: self.is_split_target(n._meta.object_type_id)
        )
        if page is None:
            return "index.md"
        return page._meta.anchor_path.removeprefix("/") + ".md"


@dataclass(frozen=True)
class Edition:
    """One report edition the generator renders — its ``paging`` policy, its
    output ``name`` (the subdirectory segment ``{outDir}/{name}/``), and the
    template surface (``templates_dir`` / ``root_template`` / ``extra_filters``)
    that renders it.

    Only the generator holds a full ``Edition``; a render's ``{% mood_view %}``
    and link filters take just its :attr:`paging`.
    """

    paging: PagingPolicy
    templates_dir: Path
    name: str = ""
    root_template: str = "index.md"
    extra_filters: Mapping[str, Callable[..., object]] = _NO_EXTRA_FILTERS
    mirror_blobs: bool = True

    @classmethod
    def from_dict(
        cls, name: str, data: Mapping[str, object], templates_dir: Path
    ) -> "Edition":
        """Build a user edition from an already-validated mapping, stamped
        with the user ``templates_dir``."""
        file_per_raw = cast(Sequence[object], data.get("file_per") or ())
        return cls(
            paging=PagingPolicy(tuple(str(p) for p in file_per_raw)),
            templates_dir=templates_dir,
            name=name,
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
