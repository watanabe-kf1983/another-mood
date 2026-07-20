"""Pipeline definition — stage factories and pipeline composition."""

from collections.abc import Callable, Sequence

from another_mood.components import (
    compose,
    derive_queries,
    generate,
    inspect_schema,
    normalize_contents,
    publish,
    reconcile,
)
from another_mood.components.shared.component.build_report import BuildReport
from another_mood.components.shared.component.dir_lock import dir_lock
from another_mood.pipeline.adapters.preparation import prepare_render
from another_mood.pipeline.base import Pipeline, ReportingStage, Stage, Task
from another_mood.pipeline.render import RenderStage, hugo_build
from another_mood.pipeline.workspace import Workspace


def inspect_schema_stage(workspace: Workspace) -> Task:
    """Validate schema.yaml against SchemaSchema."""
    config = workspace.config
    out = workspace.component_output(inspect_schema)
    call = inspect_schema.bind(
        schema_file=config.schema_file,
        out_dir=out.dir,
    )
    return Stage(run_fn=call, watch_paths=[config.schema_file])


def normalize_contents_stage(workspace: Workspace) -> Task:
    """Normalize contents_dir to normalized_contents_dir (passthrough)."""
    config = workspace.config
    inspect_out = workspace.component_output(inspect_schema)
    out = workspace.component_output(normalize_contents)
    call = normalize_contents.bind(
        src_dir=config.contents_dir,
        data_catalog_dir=inspect_out.dir,
        schema_file=config.schema_file,
        out_dir=out.dir,
        prev_out_dir=out.dir / "data",
    )
    return Stage(
        run_fn=call,
        watch_paths=[config.contents_dir],
        upstreams=[inspect_out],
    )


def derive_queries_stage(workspace: Workspace) -> Task:
    """Validate query files and derive view entities."""
    config = workspace.config
    inspect_out = workspace.component_output(inspect_schema)
    out = workspace.component_output(derive_queries)
    call = derive_queries.bind(
        queries_dir=config.queries_dir,
        data_catalog_dir=inspect_out.dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[config.queries_dir],
        upstreams=[inspect_out],
    )


def compose_stage(workspace: Workspace) -> Task:
    """Compose views from normalized contents + query evaluation."""
    contents_out = workspace.component_output(normalize_contents)
    queries_out = workspace.component_output(derive_queries)
    inspect_out = workspace.component_output(inspect_schema)
    out = workspace.component_output(compose)
    call = compose.bind(
        contents_dir=contents_out.dir,
        queries_dir=queries_out.dir,
        data_catalog_dir=inspect_out.dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[],
        upstreams=[contents_out, queries_out, inspect_out],
    )


def generator_stage(workspace: Workspace) -> Task:
    """Generate Markdown from views YAML + Jinja2 templates."""
    config = workspace.config
    compose_out = workspace.component_output(compose)
    out = workspace.component_output(generate)
    call = generate.bind(
        data_dir=compose_out.dir,
        templates_dir=config.templates_dir,
        reports_file=config.reports_file,
        project_name=config.project_dir.resolve().name,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[config.templates_dir, config.reports_file],
        upstreams=[compose_out],
    )


def reconcile_stage(workspace: Workspace) -> Task:
    """Pass Generator output through, or replace with build report on errors."""
    generate_out = workspace.component_output(generate)
    out = workspace.component_output(reconcile)
    call = reconcile.bind(
        data_dir=generate_out.dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[],
        upstreams=[generate_out],
    )


def render_stage(workspace: Workspace) -> Task:
    """Prepare Hugo content and render to HTML."""
    config = workspace.config
    return RenderStage(
        upstream=workspace.component_output(reconcile),
        prep_dir=workspace.component_output(prepare_render).dir,
        hugo_build_dir=workspace.component_output(hugo_build).dir,
        host=config.host,
        port=config.port,
    )


def publish_stage(workspace: Workspace) -> Task:
    """Copy reconciled Markdown and Hugo HTML from tmp to their public dirs.

    Watches only the terminal upstream (hugo_build): by the time it
    completes, all prior stages have settled, so we publish both outputs
    together in one cascade fire.
    """
    config = workspace.config
    reconcile_out = workspace.component_output(reconcile)
    hugo_out = workspace.component_output(hugo_build)
    publish_out = workspace.component_output(publish)
    # Publish a tree only where its destination is set (watch may set neither).
    targets = [
        (reconcile_out.dir / "data", config.out_dir),
        (hugo_out.dir / "data", config.render_dir),
    ]
    active = [(src, dist) for src, dist in targets if dist is not None]
    call = publish.bind(
        upstream=hugo_out.dir,
        out_dir=publish_out.dir,
        src_dirs=[src for src, _ in active],
        dist_dirs=[dist for _, dist in active],
    )
    return Stage(run_fn=call, watch_paths=[], upstreams=[hugo_out])


def build_report_stage(
    workspace: Workspace,
    on_report: Callable[[BuildReport], None] | None = None,
) -> ReportingStage:
    """Report build result to user. Exposes BuildReport for CLI."""
    publish_out = workspace.component_output(publish)

    def report() -> BuildReport:
        with dir_lock(publish_out.dir):
            return BuildReport.collect(publish_out.dir / "reports")

    return ReportingStage(
        report_fn=report,
        on_report=on_report,
        upstreams=[publish_out],
    )


# The pipeline's stage factories in execution order. Public so the write-once
# sweep test (tests/pipeline/test_write_once_sweep.py) drives the exact same
# stage sequence the real pipeline runs — a stage added here is automatically
# covered by the sweep.
STAGE_FACTORIES: Sequence[Callable[[Workspace], Task]] = (
    inspect_schema_stage,
    normalize_contents_stage,
    derive_queries_stage,
    compose_stage,
    generator_stage,
    reconcile_stage,
    render_stage,
    publish_stage,
)


def pipeline(
    workspace: Workspace,
    on_report: Callable[[BuildReport], None] | None = None,
) -> Pipeline:
    """Create the full pipeline."""
    stages = [factory(workspace) for factory in STAGE_FACTORIES]
    return Pipeline(stages, reporting=build_report_stage(workspace, on_report))
