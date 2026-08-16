"""Generator — render views data through Jinja2 templates to Markdown,
and reconcile the output with the propagated BuildReport.
"""

from collections.abc import Callable, Mapping, Sequence
from importlib import resources
from pathlib import Path
from typing import cast

from another_mood.components.generator.data_tree import (
    MappingNode,
    Node,
    build_node_map,
)
from another_mood.components.generator.inert import ensure_inert_mapping
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
from another_mood.components.generator.build_info_globals import (
    make_build_info_globals,
)
from another_mood.components.generator.template_engine import TemplateEngine
from another_mood.components.generator.template_safe import TemplateSafe
from another_mood.components.shared.build_info import NO_BUILD_INFO, BuildInfo
from another_mood.components.shared.component.build_report import BuildReport
from another_mood.components.shared.component.component import Component
from another_mood.components.shared.component.errors import error_propagation
from another_mood.components.shared.json_data_model import load_model
from another_mood.components.shared.transfer import link_or_copy, transfer_tree
from another_mood.components.shared.user_source.diagnostic import DiagnosticEntry
from another_mood.components.shared.windows_reserved_name import (
    ensure_not_windows_reserved,
)

_BUILD_REPORT_TEMPLATES_DIR = Path(
    str(resources.files("another_mood.resources") / "templates" / "build_report")
)

_COVER_TEMPLATES_DIR = Path(
    str(resources.files("another_mood.resources") / "templates" / "cover")
)

_NO_FILTERS: Mapping[str, Callable[..., TemplateSafe]] = {}

_BLOB_NAMESPACE = "/blob/"


@Component(out_dir="out_dir", upstream_dirs=["data_dir"])
def generate(
    data_dir: Path,
    templates_dir: Path,
    reports_file: Path,
    project_name: str,
    *,
    build_info: BuildInfo = NO_BUILD_INFO,
    out_dir: Path,
) -> None:
    """Render views data through Jinja2 templates to Markdown."""
    user_editions = load_editions(reports_file, templates_dir)
    editions = (META_EDITION, *user_editions)

    render_editions_index(editions, project_name, out_dir)

    # A page tree per edition, over the shared data model.
    node_map = build_node_map(ensure_inert_mapping(load_model(data_dir)))
    for edition in editions:
        render_edition(edition, node_map, data_dir / "contents", out_dir, build_info)


@Component(out_dir="out_dir", upstream_dirs=["data_dir"], error_propagation=False)
def reconcile(
    data_dir: Path, *, build_info: BuildInfo = NO_BUILD_INFO, out_dir: Path
) -> None:
    """Settle the output the user sees: Generator's tree as it stands, or a
    __build_failure page in its place when upstream errors propagated.  Either
    page ends with the ``build_info`` colophon.
    """
    with error_propagation([data_dir], out_dir, component="reconcile") as ctx:
        if ctx is not None:
            transfer_tree(ctx.upstreams[0], ctx.out, dirs_exist_ok=True)
            warnings = [
                d
                for d in BuildReport.collect(data_dir / "reports").diagnostics
                if d.severity == "warning"
            ]
            tail = [_colophon(build_info, out_dir)]
            if warnings:
                tail = [_warnings_section(warnings, ctx.out), *tail]
            _append_tail(ctx.out / "index.md", tail)
        else:
            report = BuildReport.collect(data_dir / "reports")
            markdown_engine(
                out_dir / "data", _BUILD_REPORT_TEMPLATES_DIR
            ).render_to_file(
                "build_failure.md",
                {**report.to_data(), "build_info": build_info},
                Path("index.md"),
            )


def _colophon(build_info: BuildInfo, out_dir: Path) -> str:
    """The colophon as a trailing section for the cover, which the generation
    side renders — the failure page includes the same template itself."""
    engine = markdown_engine(out_dir, _BUILD_REPORT_TEMPLATES_DIR)
    return engine.render("colophon.md", {"build_info": build_info})


def _warnings_section(warnings: Sequence[DiagnosticEntry], out: Path) -> str:
    """Render the warnings page under ``out``, and return the section that
    links to it."""
    markdown_engine(out / "__warnings", _BUILD_REPORT_TEMPLATES_DIR).render_to_file(
        "warnings.md",
        {"diagnostics": [d.to_data() for d in warnings]},
        Path("index.md"),
    )
    count = len(warnings)
    label = f"{count} warning{'' if count == 1 else 's'}"
    return f"## Warnings\n\n{label} — [view](__warnings/)\n"


def _append_tail(index_md: Path, sections: Sequence[str]) -> None:
    present = [section for section in sections if section]
    if not present:
        return
    content = index_md.read_text(encoding="utf-8")
    # Replace the file, never append in place: the inode may be shared
    # with the upstream copy via hardlink.
    index_md.unlink()
    index_md.write_text("\n".join([content, *present]), encoding="utf-8")


def render_editions_index(
    editions: Sequence[Edition], project_name: str, out_dir: Path
) -> None:
    """Render the root cover listing the editions (no data model, no filters)."""
    # Project each edition to the fields the cover reads: the render boundary
    # marshals subjects to inert, and a live Edition (callables / paths) is not.
    markdown_engine(out_dir, _COVER_TEMPLATES_DIR).render_to_file(
        "index.md",
        {
            "editions": [
                {
                    "name": e.name,
                    "dir_segment": e.dir_segment,
                    "is_system": e.is_system,
                }
                for e in editions
            ],
            "project_name": project_name,
        },
        Path("index.md"),
    )


def render_edition(
    edition: Edition,
    node_map: Mapping[str, Node],
    blobs_dir: Path,
    out_dir: Path,
    build_info: BuildInfo = NO_BUILD_INFO,
) -> None:
    """Render one edition's page tree to its mount ``out_dir/<dir_segment>/``
    and mirror its blob resources (when ``edition.mirror_blobs``) from
    ``blobs_dir`` (blob bytes at their contents-relative paths)."""
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
        globals={**node_globals, **make_build_info_globals(build_info)},
        paging=edition.paging,
    ).render_to_file(edition.root_template, data, Path("index.md"))
    if edition.mirror_blobs:
        _copy_blobs(node_map, blobs_dir, root)


def _copy_blobs(node_map: Mapping[str, Node], blobs_dir: Path, root: Path) -> None:
    """Mirror each blob's bytes from ``blobs_dir`` to ``root/blob/<id>``."""
    for path, node in node_map.items():
        if path.startswith(_BLOB_NAMESPACE):
            src = blobs_dir / cast(str, cast(MappingNode, node)["id"])
            dest = root / path.removeprefix("/")
            dest.parent.mkdir(parents=True, exist_ok=True)
            link_or_copy(src, dest)


def markdown_engine(
    out_dir: Path,
    templates_dir: Path,
    *,
    filters: Mapping[str, Callable[..., TemplateSafe]] = _NO_FILTERS,
    globals: Mapping[str, Callable[..., TemplateSafe]] = _NO_FILTERS,
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
