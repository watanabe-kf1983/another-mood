"""Pipeline definition — stage factories and pipeline composition."""

import sys
from datetime import datetime

from reqs_builder.components import (
    compose,
    generate,
    inspect_schema,
    normalize_contents,
    normalize_queries,
)
from reqs_builder.components.shared.build_report import BuildReport
from reqs_builder.config import ProjectConfig
from reqs_builder.pipeline.base import Pipeline, ReportingStage, Stage, Task
from reqs_builder.pipeline.render import RenderStage


def inspect_schema_stage(config: ProjectConfig) -> Task:
    """Validate schema files against SchemaSchema."""
    call = inspect_schema.bind(
        schema_dir=config.schema_dir,
        out_dir=config.data_catalog_dir,
    )
    return Stage(run_fn=call, watch_paths=[config.schema_dir])


def normalize_contents_stage(config: ProjectConfig) -> Task:
    """Normalize contents_dir to normalized_contents_dir (passthrough)."""
    call = normalize_contents.bind(
        src_dir=config.contents_dir,
        data_catalog_dir=config.data_catalog_dir,
        schema_dir=config.schema_dir,
        out_dir=config.normalized_contents_dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[config.contents_dir, config.data_catalog_dir],
    )


def normalize_queries_stage(config: ProjectConfig) -> Task:
    """Validate and normalize query files."""
    call = normalize_queries.bind(
        queries_dir=config.queries_dir,
        out_dir=config.normalized_queries_dir,
    )
    return Stage(run_fn=call, watch_paths=[config.queries_dir])


def compose_stage(config: ProjectConfig) -> Task:
    """Compose views from normalized contents + query evaluation."""
    call = compose.bind(
        contents_dir=config.normalized_contents_dir,
        queries_dir=config.normalized_queries_dir,
        out_dir=config.views_dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[config.normalized_contents_dir, config.normalized_queries_dir],
    )


def generator_stage(config: ProjectConfig) -> Task:
    """Generate Markdown from views YAML + Jinja2 templates."""
    call = generate.bind(
        data_dir=config.views_dir,
        templates_dir=config.templates_dir,
        out_dir=config.out_dir,
    )
    return Stage(
        run_fn=call,
        watch_paths=[config.views_dir, config.templates_dir],
    )


def render_stage(config: ProjectConfig) -> Task:
    """Prepare Hugo content and render to HTML."""
    return RenderStage(
        src_dir=config.out_dir,
        render_input_dir=config.render_in_dir,
        render_output_dir=config.render_out_dir,
        port=config.port,
    )


def build_report_stage(config: ProjectConfig) -> ReportingStage:
    """Report build result to user. Exposes BuildReport for CLI."""
    first = True

    def report() -> BuildReport:
        nonlocal first
        result = BuildReport.collect(config.out_dir)
        succeeded = not result.has_errors()
        messages = {
            (True, True): "Build successfully completed",
            (True, False): "Build failed",
            (False, True): "Files updated, and re-build successfully completed",
            (False, False): "Files updated, but re-build failed",
        }
        msg = messages[first, succeeded]
        first = False
        print(f"{msg} at {datetime.now():%H:%M:%S}.", file=sys.stderr, flush=True)
        return result

    return ReportingStage(report_fn=report, watch_paths=[config.out_dir])


def pipeline(config: ProjectConfig) -> Pipeline:
    """Create the full pipeline."""
    stages: list[Task] = [
        inspect_schema_stage(config),
        normalize_contents_stage(config),
        normalize_queries_stage(config),
        compose_stage(config),
        generator_stage(config),
        render_stage(config),
    ]
    return Pipeline(stages, reporting=build_report_stage(config))
