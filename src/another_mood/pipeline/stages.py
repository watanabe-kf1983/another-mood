"""Pipeline definition — stage factories and pipeline composition."""

from collections.abc import Callable, Sequence
from pathlib import Path

from another_mood.components import (
    compose,
    derive_queries,
    generate,
    inspect_schema,
    normalize_contents,
    publish,
    reconcile,
    tap,
    tap_schema,
)
from another_mood.components.shared.component.build_report import BuildReport
from another_mood.components.shared.component.component import ComponentCall
from another_mood.components.shared.component.dir_lock import dir_lock
from another_mood.pipeline.adapters.preparation import prepare_site
from another_mood.pipeline.base import (
    ComponentOutput,
    Pipeline,
    ReportingStage,
    Stage,
    Task,
)
from another_mood.pipeline.site import SiteServeStage, SiteStage, hugo_build
from another_mood.pipeline.workspace import Workspace


def inspect_schema_stage(workspace: Workspace) -> Task:
    """Validate schema.yaml against SchemaSchema."""
    layout = workspace.layout
    out = workspace.component_output(inspect_schema)
    call = inspect_schema.bind(
        schema_file=layout.schema_file,
        out_dir=out.dir,
    )
    return Stage(run_fn=call, watch_paths=[layout.schema_file])


def normalize_contents_stage(workspace: Workspace) -> Task:
    """Normalize contents_dir to normalized_contents_dir (passthrough)."""
    layout = workspace.layout
    inspect_out = workspace.component_output(inspect_schema)
    out = workspace.component_output(normalize_contents)
    call = normalize_contents.bind(
        src_dir=layout.contents_dir,
        data_catalog_dir=inspect_out.dir,
        schema_file=layout.schema_file,
        out_dir=out.dir,
        prev_out_dir=out.dir / "data",
    )
    return Stage(
        run_fn=call,
        watch_paths=[layout.contents_dir],
        upstreams=[inspect_out],
    )


def derive_queries_stage(workspace: Workspace) -> Task:
    """Validate view files and derive view entities."""
    layout = workspace.layout
    inspect_out = workspace.component_output(inspect_schema)
    out = workspace.component_output(derive_queries)
    call = derive_queries.bind(
        views_dir=layout.views_dir,
        data_catalog_dir=inspect_out.dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[layout.views_dir],
        upstreams=[inspect_out],
    )


def compose_stage(workspace: Workspace) -> Task:
    """Compose views from normalized contents + query evaluation."""
    contents_out = workspace.component_output(normalize_contents)
    catalog_out = workspace.component_output(derive_queries)
    out = workspace.component_output(compose)
    call = compose.bind(
        contents_dir=contents_out.dir,
        catalog_dir=catalog_out.dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[],
        upstreams=[contents_out, catalog_out],
    )


def tap_stage(workspace: Workspace) -> Task:
    """Assemble the composed namespace into one JSON document."""
    compose_out = workspace.component_output(compose)
    out = workspace.component_output(tap)
    call = tap.bind(
        data_dir=compose_out.dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[],
        upstreams=[compose_out],
    )


def tap_schema_stage(workspace: Workspace) -> Task:
    """Describe the tap document with a JSON Schema derived from the catalog."""
    derive_out = workspace.component_output(derive_queries)
    out = workspace.component_output(tap_schema)
    call = tap_schema.bind(
        catalog_dir=derive_out.dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[],
        upstreams=[derive_out],
    )


def generator_stage(workspace: Workspace) -> Task:
    """Generate Markdown from views YAML + Jinja2 templates."""
    layout = workspace.layout
    compose_out = workspace.component_output(compose)
    out = workspace.component_output(generate)
    call = generate.bind(
        data_dir=compose_out.dir,
        templates_dir=layout.templates_dir,
        reports_file=layout.reports_file,
        project_name=workspace.manifest.title
        or workspace.config.project_dir.resolve().name,
        build_info=workspace.build_info,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[layout.templates_dir, layout.reports_file],
        upstreams=[compose_out],
    )


def reconcile_stage(workspace: Workspace) -> Task:
    """Pass Generator output through, or replace with build report on errors."""
    generate_out = workspace.component_output(generate)
    out = workspace.component_output(reconcile)
    call = reconcile.bind(
        data_dir=generate_out.dir,
        build_info=workspace.build_info,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[],
        upstreams=[generate_out],
    )


def site_stage(workspace: Workspace) -> Task:
    """Prepare Hugo content and render it to a static site."""
    return SiteStage(
        upstream=workspace.component_output(reconcile),
        prep_dir=workspace.component_output(prepare_site).dir,
        hugo_build_dir=workspace.component_output(hugo_build).dir,
    )


def site_serve_stage(workspace: Workspace) -> Task:
    """Prepare Hugo content and serve it live."""
    config = workspace.config
    return SiteServeStage(
        upstream=workspace.component_output(reconcile),
        prep_dir=workspace.component_output(prepare_site).dir,
        host=config.host,
        port=config.port,
    )


def publish_stage(workspace: Workspace) -> Task:
    """Copy reconciled Markdown and Hugo HTML from tmp to their public dirs."""
    config = workspace.config
    reconcile_out = workspace.component_output(reconcile)
    hugo_out = workspace.component_output(hugo_build)
    return _publish_stage(
        workspace,
        # The terminal upstream: its reports carry every earlier stage's.
        upstream=hugo_out,
        targets=[
            (reconcile_out.dir / "data", config.out_dir),
            (hugo_out.dir / "data", config.site_dir),
        ],
    )


def watch_publish_stage(workspace: Workspace) -> Task:
    """Copy reconciled Markdown from tmp to out_dir."""
    # Watches reconcile, not prepare_site: prepare_site rewrites its data/ and
    # static/ in place under their own locks, which exclusive_read's
    # prepare_site.lock does not exclude, so files would vanish mid-copy.
    reconcile_out = workspace.component_output(reconcile)
    return _publish_stage(
        workspace,
        upstream=reconcile_out,
        targets=[(reconcile_out.dir / "data", workspace.config.out_dir)],
    )


def _publish_stage(
    workspace: Workspace,
    *,
    upstream: ComponentOutput,
    targets: Sequence[tuple[Path, Path | None]],
) -> Task:
    publish_out = workspace.component_output(publish)
    # Publish a tree only where its destination is set.
    active = [(src, dist) for src, dist in targets if dist is not None]
    call = publish.bind(
        upstream=upstream.dir,
        out_dir=publish_out.dir,
        src_dirs=[src for src, _ in active],
        dist_dirs=[dist for _, dist in active],
    )
    return Stage(run_fn=call, watch_paths=[], upstreams=[upstream])


def build_report_stage(
    workspace: Workspace,
    source: ComponentCall,
    on_report: Callable[[BuildReport], None] | None = None,
) -> ReportingStage:
    """Report build result to user. Exposes BuildReport for CLI.

    ``source`` is the pipeline's terminal component: errors propagate to its
    reports, so that is where they are collected from.
    """
    source_out = workspace.component_output(source)

    def report() -> BuildReport:
        with dir_lock(source_out.dir):
            return BuildReport.collect(source_out.dir / "reports")

    return ReportingStage(
        report_fn=report,
        on_report=on_report,
        upstreams=[source_out],
    )


# Each pipeline's stage factories, in execution order, sit right before the
# function that runs them. A list is spelled out in full rather than sliced
# from the build list, so a stage added to one pipeline joins another only by
# an explicit decision. Public so the write-once sweep test
# (tests/pipeline/test_write_once_sweep.py) drives the exact sequence each
# pipeline runs: a stage added to a list is automatically covered by the sweep.

BUILD_STAGE_FACTORIES: Sequence[Callable[[Workspace], Task]] = (
    inspect_schema_stage,
    normalize_contents_stage,
    derive_queries_stage,
    compose_stage,
    generator_stage,
    reconcile_stage,
    site_stage,
    publish_stage,
)


def build_pipeline(
    workspace: Workspace,
    on_report: Callable[[BuildReport], None] | None = None,
) -> Pipeline:
    """Create the build pipeline."""
    stages = [factory(workspace) for factory in BUILD_STAGE_FACTORIES]
    return Pipeline(stages, reporting=build_report_stage(workspace, publish, on_report))


WATCH_STAGE_FACTORIES: Sequence[Callable[[Workspace], Task]] = (
    inspect_schema_stage,
    normalize_contents_stage,
    derive_queries_stage,
    compose_stage,
    generator_stage,
    reconcile_stage,
    site_serve_stage,
)

# watch with --out-dir publishes the Markdown tree as well
# (docs/reference/cli.md › --out-dir).
WATCH_PUBLISH_STAGE_FACTORIES: Sequence[Callable[[Workspace], Task]] = (
    *WATCH_STAGE_FACTORIES,
    watch_publish_stage,
)


def watch_pipeline(
    workspace: Workspace,
    on_report: Callable[[BuildReport], None] | None = None,
) -> Pipeline:
    """Create the watch pipeline: serve the site live instead of building it,
    and publish the Markdown tree only when out_dir is set."""
    if workspace.config.out_dir is None:
        factories, source = WATCH_STAGE_FACTORIES, reconcile
    else:
        factories, source = WATCH_PUBLISH_STAGE_FACTORIES, publish
    stages = [factory(workspace) for factory in factories]
    return Pipeline(stages, reporting=build_report_stage(workspace, source, on_report))


TAP_STAGE_FACTORIES: Sequence[Callable[[Workspace], Task]] = (
    inspect_schema_stage,
    normalize_contents_stage,
    derive_queries_stage,
    compose_stage,
    tap_stage,
)


def tap_pipeline(workspace: Workspace) -> Pipeline:
    """Create the tap pipeline: stop after compose, assemble one JSON document."""
    stages = [factory(workspace) for factory in TAP_STAGE_FACTORIES]
    return Pipeline(stages, reporting=build_report_stage(workspace, tap))


# The schema needs only the catalog, which derive_queries completes: contents
# are not read, and views are evaluated downstream of it but declared within it.
TAP_SCHEMA_STAGE_FACTORIES: Sequence[Callable[[Workspace], Task]] = (
    inspect_schema_stage,
    derive_queries_stage,
    tap_schema_stage,
)


def tap_schema_pipeline(workspace: Workspace) -> Pipeline:
    """Create the tap schema pipeline: stop after derive_queries, write the
    tap document's JSON Schema."""
    stages = [factory(workspace) for factory in TAP_SCHEMA_STAGE_FACTORIES]
    return Pipeline(stages, reporting=build_report_stage(workspace, tap_schema))
