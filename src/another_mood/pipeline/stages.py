"""Pipeline definition — stage factories and pipeline composition."""

from collections.abc import Callable

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
from another_mood.config import ProjectConfig
from another_mood.pipeline.adapters.preparation import prepare_render
from another_mood.pipeline.base import Pipeline, ReportingStage, Stage, Task
from another_mood.pipeline.render import RenderStage, hugo_build


def inspect_schema_stage(config: ProjectConfig) -> Task:
    """Validate schema.yaml against SchemaSchema."""
    out = config.component_output(inspect_schema)
    call = inspect_schema.bind(
        schema_file=config.schema_file,
        out_dir=out.dir,
    )
    return Stage(run_fn=call, watch_paths=[config.schema_file])


def normalize_contents_stage(config: ProjectConfig) -> Task:
    """Normalize contents_dir to normalized_contents_dir (passthrough)."""
    inspect_out = config.component_output(inspect_schema)
    out = config.component_output(normalize_contents)
    call = normalize_contents.bind(
        src_dir=config.contents_dir,
        data_catalog_dir=inspect_out.dir,
        schema_file=config.schema_file,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[config.contents_dir],
        upstreams=[inspect_out],
    )


def derive_queries_stage(config: ProjectConfig) -> Task:
    """Validate query files and derive view entities."""
    inspect_out = config.component_output(inspect_schema)
    out = config.component_output(derive_queries)
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


def compose_stage(config: ProjectConfig) -> Task:
    """Compose views from normalized contents + query evaluation."""
    contents_out = config.component_output(normalize_contents)
    queries_out = config.component_output(derive_queries)
    inspect_out = config.component_output(inspect_schema)
    out = config.component_output(compose)
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


def generator_stage(config: ProjectConfig) -> Task:
    """Generate Markdown from views YAML + Jinja2 templates."""
    compose_out = config.component_output(compose)
    out = config.component_output(generate)
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


def reconcile_stage(config: ProjectConfig) -> Task:
    """Pass Generator output through, or replace with build report on errors."""
    generate_out = config.component_output(generate)
    out = config.component_output(reconcile)
    call = reconcile.bind(
        data_dir=generate_out.dir,
        out_dir=out.dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[],
        upstreams=[generate_out],
    )


def render_stage(config: ProjectConfig) -> Task:
    """Prepare Hugo content and render to HTML."""
    return RenderStage(
        upstream=config.component_output(reconcile),
        prep_dir=config.component_output(prepare_render).dir,
        hugo_build_dir=config.component_output(hugo_build).dir,
        host=config.host,
        port=config.port,
    )


def publish_stage(config: ProjectConfig) -> Task:
    """Copy reconciled Markdown and Hugo HTML from tmp to their public dirs.

    Watches only the terminal upstream (hugo_build): by the time it
    completes, all prior stages have settled, so we publish both outputs
    together in one cascade fire.
    """
    reconcile_out = config.component_output(reconcile)
    hugo_out = config.component_output(hugo_build)
    publish_out = config.component_output(publish)
    call = publish.bind(
        upstream=hugo_out.dir,
        out_dir=publish_out.dir,
        src_dirs=[reconcile_out.dir / "data", hugo_out.dir / "data"],
        dist_dirs=[config.out_dir, config.render_dir],
    )
    return Stage(run_fn=call, watch_paths=[], upstreams=[hugo_out])


def build_report_stage(
    config: ProjectConfig,
    on_report: Callable[[BuildReport], None] | None = None,
) -> ReportingStage:
    """Report build result to user. Exposes BuildReport for CLI."""
    publish_out = config.component_output(publish)

    def report() -> BuildReport:
        with dir_lock(publish_out.dir):
            return BuildReport.collect(publish_out.dir / "reports")

    return ReportingStage(
        report_fn=report,
        on_report=on_report,
        upstreams=[publish_out],
    )


def pipeline(
    config: ProjectConfig,
    on_report: Callable[[BuildReport], None] | None = None,
) -> Pipeline:
    """Create the full pipeline."""
    stages: list[Task] = [
        inspect_schema_stage(config),
        normalize_contents_stage(config),
        derive_queries_stage(config),
        compose_stage(config),
        generator_stage(config),
        reconcile_stage(config),
        render_stage(config),
        publish_stage(config),
    ]
    return Pipeline(stages, reporting=build_report_stage(config, on_report))
