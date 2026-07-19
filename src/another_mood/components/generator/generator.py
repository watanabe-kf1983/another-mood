"""Generator — render views data through Jinja2 templates to Markdown,
and reconcile the output with the propagated BuildReport.
"""

import shutil
from collections.abc import Callable, Mapping
from importlib import resources
from pathlib import Path
from typing import Any, cast

from another_mood.components.generator.data_tree import (
    MappingNode,
    Node,
    build_node_map,
)
from another_mood.components.generator.data_tree_filters import make_data_tree_filters
from another_mood.components.generator.edition import (
    Edition,
    PagingPolicy,
    load_editions,
)
from another_mood.components.generator.meta_templates import META_EDITION
from another_mood.components.generator.output_formats.md import (
    MD,
    MD_FILTERS,
    MD_GLOBALS,
    make_link_filters,
)
from another_mood.components.generator.template_engine import TemplateEngine
from another_mood.components.shared.component.build_report import BuildReport
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.component.errors import error_propagation
from another_mood.components.shared.json_data_model import load_model
from another_mood.components.shared.transfer import transfer_tree
from another_mood.components.shared.windows_reserved_name import (
    ensure_not_windows_reserved,
)

_BUILD_REPORT_TEMPLATES_DIR = Path(
    str(resources.files("another_mood.resources") / "templates" / "build_report")
)

_COVER_TEMPLATES_DIR = Path(
    str(resources.files("another_mood.resources") / "templates" / "cover")
)

_NO_FILTERS: Mapping[str, Callable[..., Any]] = {}

_BLOB_NAMESPACE = "/blob/"


@Component(out_dir="out_dir", upstream_dirs=["data_dir"])
def generate(
    data_dir: Path,
    templates_dir: Path,
    reports_file: Path,
    contents_dir: Path,
    project_name: str,
    *,
    out_dir: Path,
) -> None:
    """Render views data through Jinja2 templates to Markdown."""
    user_editions = load_editions(reports_file, templates_dir)
    editions = (META_EDITION, *user_editions)

    # The root cover just lists the editions — no data model, so no filters.
    markdown_engine(out_dir, _COVER_TEMPLATES_DIR).render_to_file(
        "index.md",
        {"editions": editions, "project_name": project_name},
        Path("index.md"),
    )

    # A page tree per edition, over the shared data model.
    node_map = build_node_map(load_model(data_dir))
    for edition in editions:
        render_edition(edition, node_map, contents_dir, out_dir)


@Component(out_dir="out_dir", upstream_dirs=["data_dir"], error_propagation=False)
def reconcile(data_dir: Path, *, out_dir: Path) -> None:
    """Reconcile Generator output with the propagated BuildReport.

    No upstream errors: pass Generator's data through.  When the
    propagated report carries warning diagnostics, render a
    ``__warnings/`` page and link to it from ``index.md``.

    Upstream errors: render a __build_failure page in its place.
    """
    with error_propagation([data_dir], out_dir, component="reconcile") as ctx:
        if ctx is not None:
            transfer_tree(ctx.upstreams[0], ctx.out, dirs_exist_ok=True)
            warnings = [
                d
                for d in BuildReport.collect(data_dir / "reports").diagnostics
                if d.severity == "warning"
            ]
            if warnings:
                markdown_engine(
                    ctx.out / "__warnings", _BUILD_REPORT_TEMPLATES_DIR
                ).render_to_file(
                    "warnings.md",
                    {"diagnostics": [d.to_data() for d in warnings]},
                    Path("index.md"),
                )
                _append_warnings_link(ctx.out / "index.md", len(warnings))
        else:
            report = BuildReport.collect(data_dir / "reports")
            markdown_engine(
                out_dir / "data", _BUILD_REPORT_TEMPLATES_DIR
            ).render_to_file(
                "build_failure.md",
                report.to_data(),
                Path("index.md"),
            )


def _append_warnings_link(index_md: Path, count: int) -> None:
    """Append a short ``## Warnings`` block linking to the warnings page."""
    label = f"{count} warning{'' if count == 1 else 's'}"
    content = index_md.read_text(encoding="utf-8")
    # Replace the file, never append in place: the inode may be shared
    # with the upstream copy via hardlink.
    index_md.unlink()
    index_md.write_text(
        f"{content}\n## Warnings\n\n{label} — [view](__warnings/)\n", encoding="utf-8"
    )


def render_edition(
    edition: Edition,
    node_map: Mapping[str, Node],
    contents_dir: Path,
    out_dir: Path,
) -> None:
    """Render one edition's page tree to its mount ``out_dir/<dir_segment>/``
    and mirror its blob resources (when ``edition.mirror_blobs``)."""
    data = cast(MappingNode, node_map["/"])
    node_globals, node_filters = make_data_tree_filters(node_map)
    root = ensure_not_windows_reserved(out_dir / edition.dir_segment)
    markdown_engine(
        root,
        edition.templates_dir,
        filters={
            **edition.extra_filters,
            **node_filters,
            **make_link_filters(edition.paging, node_map),
        },
        globals=node_globals,
        paging=edition.paging,
    ).render_to_file(edition.root_template, data, Path("index.md"))
    if edition.mirror_blobs:
        _copy_blobs(node_map, contents_dir, root)


def _copy_blobs(node_map: Mapping[str, Node], contents_dir: Path, root: Path) -> None:
    """Copy each blob's bytes from ``contents_dir`` to ``root/blob/<id>``.

    A real copy, never a hardlink: a shared inode lets an in-place source
    edit corrupt already-published output.
    """
    for path, node in node_map.items():
        if path.startswith(_BLOB_NAMESPACE):
            src = contents_dir / cast(str, cast(MappingNode, node)["id"])
            dest = root / path.removeprefix("/")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def markdown_engine(
    out_dir: Path,
    templates_dir: Path,
    *,
    filters: Mapping[str, Callable[..., Any]] = _NO_FILTERS,
    globals: Mapping[str, Callable[..., Any]] = _NO_FILTERS,
    paging: PagingPolicy = PagingPolicy(),
) -> TemplateEngine:
    """A ``TemplateEngine`` bound to the Markdown output format and its helpers.

    The md format's own filters/globals are merged in here so every caller gets
    them; the caller adds any edition / node-map-bound ``filters`` on top and
    drives ``render_to_file`` with its own destination.
    """
    return TemplateEngine(
        out_dir,
        templates_dir=templates_dir,
        output_format=MD,
        filters={**MD_FILTERS, **filters},
        globals={**MD_GLOBALS, **globals},
        paging=paging,
    )
